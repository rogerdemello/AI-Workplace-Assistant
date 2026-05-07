"""
Comprehensive demo data seeder for MARK HR dashboard.

Creates realistic employees, tickets, conversations, sentiment logs,
employee scores, and risk snapshots so the HR dashboard is fully populated.

Run from the `backend` directory:

  python -m scripts.seed_demo_data

Idempotent: safe to run multiple times (clears old demo data first).
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta, date
from uuid import uuid4
import random

# Resolve package root (backend/)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import app.models  # noqa: F401 — register all models with Base.metadata
from sqlalchemy import text

from app.auth.password import hash_password
from app.database import Base, SessionLocal, engine
from app.core.time import utcnow_naive
from app.models.department import Department
from app.models.user import User, UserRole, UserStatus
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.conversation import Conversation, Message, MessageSender
from app.models.sentiment_log import SentimentLog
from app.models.employee_score import EmployeeScore
from app.models.risk_snapshot import RiskSnapshot
from app.models.hr_notification import HrNotification
from app.models.leave_request import LeaveRequest, LeaveStatus, LeaveType

DEFAULT_PASSWORD = "password123"

def _hash():
    return hash_password(DEFAULT_PASSWORD)

DEPARTMENTS = [
    ("Engineering", "Product and platform engineering"),
    ("People Ops", "HR and talent management"),
    ("Sales", "Revenue and customer success"),
    ("Design", "Product design and UX"),
]

EMPLOYEES = [
    # (email, name, employee_id, designation, department_idx, manager_idx_or_none, role)
    ("hr1@infeedo.ai", "HR One", "HR-1", "HR Business Partner", 1, None, UserRole.hr),
    ("manager1@infeedo.ai", "Alice Chen", "MGR-1", "Engineering Manager", 0, None, UserRole.manager),
    ("manager2@infeedo.ai", "Bob Patel", "MGR-2", "Sales Director", 2, None, UserRole.manager),
    ("emp1@infeedo.ai", "Carol Williams", "EMP-1", "Senior Engineer", 0, 1, UserRole.employee),
    ("emp2@infeedo.ai", "David Kim", "EMP-2", "Backend Engineer", 0, 1, UserRole.employee),
    ("emp3@infeedo.ai", "Eva Martinez", "EMP-3", "Frontend Engineer", 0, 1, UserRole.employee),
    ("emp4@infeedo.ai", "Frank Liu", "EMP-4", "DevOps Engineer", 0, 1, UserRole.employee),
    ("emp5@infeedo.ai", "Grace Okafor", "EMP-5", "Sales Executive", 2, 2, UserRole.employee),
    ("emp6@infeedo.ai", "Hassan Ali", "EMP-6", "Account Manager", 2, 2, UserRole.employee),
    ("emp7@infeedo.ai", "Ivan Petrov", "EMP-7", "UX Designer", 3, None, UserRole.employee),
    ("emp8@infeedo.ai", "Julia Schmidt", "EMP-8", "Product Designer", 3, None, UserRole.employee),
]

TICKET_TEMPLATES = [
    ("Laptop screen flickering", "hardware", TicketPriority.high),
    ("Request for ergonomic chair", "facilities", TicketPriority.medium),
    ("Payroll discrepancy for March", "payroll", TicketPriority.high),
    ("Uncomfortable with team lead behavior", "complaint", TicketPriority.critical),
    ("Need access to staging environment", "access", TicketPriority.medium),
    ("Vacation approval pending for 2 weeks", "leave", TicketPriority.low),
    ("Harassment report - need to talk", "complaint", TicketPriority.critical),
    ("Health insurance not reflecting dependents", "benefits", TicketPriority.medium),
    ("VPN keeps disconnecting", "it_support", TicketPriority.medium),
    ("Request for training budget", "learning", TicketPriority.low),
    ("Overwhelmed with current workload", "wellbeing", TicketPriority.high),
    ("Team conflict escalation needed", "complaint", TicketPriority.high),
]

SENTIMENT_MESSAGES = [
    ("I am really happy with the new project!", "positive", "satisfaction", 82),
    ("The workload is getting too much to handle", "negative", "overwhelm", 22),
    ("Great team lunch today, feeling connected", "positive", "joy", 78),
    ("I feel burnt out and need a break", "negative", "burnout", 15),
    ("Not sure about the new policy changes", "neutral", "confusion", 48),
    ("Frustrated with slow approval processes", "negative", "frustration", 28),
    ("My manager has been very supportive", "positive", "gratitude", 85),
    ("Anxious about the upcoming deadline", "negative", "anxiety", 32),
    ("Everything is going fine, no issues", "neutral", "neutral", 55),
    ("I am extremely stressed and can't cope", "negative", "panic", 12),
    ("Love the remote work flexibility", "positive", "satisfaction", 80),
    ("Feeling isolated from the team lately", "negative", "loneliness", 35),
]


def _safe_delete(db, sql, params):
    try:
        db.execute(text(sql), params)
    except Exception:
        db.rollback()


def clear_demo_data(db):
    """Remove previously seeded demo rows to stay idempotent."""
    demo_emails = [e[0] for e in EMPLOYEES]
    demo_users = db.query(User).filter(User.email.in_(demo_emails)).all()
    demo_user_ids = [u.id for u in demo_users]
    if not demo_user_ids:
        return
    ids = tuple(demo_user_ids)
    # Delete in dependency order (child tables first)
    tables = [
        "wellbeing_signals",
        "sentiment_logs",
        "employee_scores",
        "risk_snapshots",
        "chat_feedback",
        "conversation_memory",
        "ticket_messages",
        "ticket_action_logs",
        "tickets",
        "messages",
        "conversations",
        "leave_requests",
        "hr_notifications",
        "personal_facts",
        "appreciation_notes",
        "mood_entries",
        "activity_events",
    ]
    for table in tables:
        _safe_delete(db, f"DELETE FROM {table} WHERE user_id IN :ids", {"ids": ids})
        for col in ["actor_id", "employee_id", "sender_id", "created_by"]:
            _safe_delete(db, f"DELETE FROM {table} WHERE {col} IN :ids", {"ids": ids})
    _safe_delete(db, "DELETE FROM tickets WHERE user_id IN :ids", {"ids": ids})
    _safe_delete(db, "DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id IN :ids)", {"ids": ids})
    _safe_delete(db, "DELETE FROM conversations WHERE user_id IN :ids", {"ids": ids})
    _safe_delete(db, "DELETE FROM users WHERE id IN :ids", {"ids": ids})
    db.commit()


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        clear_demo_data(db)

        # Create departments
        depts = []
        for name, desc in DEPARTMENTS:
            d = db.query(Department).filter(Department.name == name).first()
            if not d:
                d = Department(name=name, description=desc)
                db.add(d)
                db.flush()
            depts.append(d)

        # Create users
        users = []
        user_by_idx = {}
        for i, (email, name, eid, designation, dept_idx, mgr_idx, role) in enumerate(EMPLOYEES):
            mgr_id = user_by_idx.get(mgr_idx) if mgr_idx is not None else None
            user = User(
                id=uuid4(),
                email=email,
                name=name,
                employee_id=eid,
                hashed_password=_hash(),
                role=role,
                designation=designation,
                status=UserStatus.active,
                department_id=depts[dept_idx].id if dept_idx < len(depts) else None,
                manager_id=mgr_id,
            )
            db.add(user)
            db.flush()
            users.append(user)
            user_by_idx[i] = user.id
            print(f"  User: {name} ({role.value})")

        hr_user = users[0]
        employee_users = [u for u in users if u.role == UserRole.employee]

        # Create tickets
        tickets = []
        now = utcnow_naive()
        for i, (title, category, priority) in enumerate(TICKET_TEMPLATES):
            user = random.choice(employee_users)
            created = now - timedelta(hours=random.randint(1, 168))
            status_pool = [TicketStatus.open, TicketStatus.open, TicketStatus.in_progress, TicketStatus.resolved, TicketStatus.escalated]
            status = random.choice(status_pool)
            assigned = hr_user.id if status != TicketStatus.open else None
            resolved = created + timedelta(hours=random.randint(2, 48)) if status == TicketStatus.resolved else None
            ticket = Ticket(
                id=uuid4(),
                user_id=user.id,
                query=title,
                category=category,
                status=status,
                priority=priority,
                assigned_to=assigned,
                created_at=created,
                updated_at=resolved or created,
                resolved_at=resolved,
                sentiment_score=random.randint(20, 85),
            )
            db.add(ticket)
            tickets.append(ticket)
        db.flush()
        print(f"  Tickets: {len(tickets)}")

        # Create conversations, messages, and sentiment logs
        sentiment_logs = []
        conversations = []
        for emp in employee_users:
            # 1-3 conversations per employee
            for _ in range(random.randint(1, 3)):
                conv = Conversation(
                    id=uuid4(),
                    user_id=emp.id,
                    status="active",
                    started_at=now - timedelta(days=random.randint(1, 14), hours=random.randint(0, 23)),
                )
                db.add(conv)
                conversations.append(conv)
                db.flush()

                # 2-6 messages per conversation
                for msg_idx in range(random.randint(2, 6)):
                    msg_text, label, emotion, score = random.choice(SENTIMENT_MESSAGES)
                    msg = Message(
                        id=uuid4(),
                        conversation_id=conv.id,
                        sender=MessageSender.user if msg_idx % 2 == 0 else MessageSender.bot,
                        message_text=msg_text,
                        created_at=conv.started_at + timedelta(minutes=msg_idx * 5),
                    )
                    db.add(msg)
                    db.flush()

                    if msg.sender == MessageSender.user:
                        log = SentimentLog(
                            id=uuid4(),
                            employee_id=emp.id,
                            conversation_id=conv.id,
                            message_id=msg.id,
                            score=score,
                            label=label,
                            emotion=emotion,
                            analysis_source=random.choice(["llm", "hybrid", "lexicon"]),
                            created_at=msg.created_at,
                        )
                        db.add(log)
                        sentiment_logs.append(log)
        db.flush()
        print(f"  Conversations: {len(conversations)}, Sentiment logs: {len(sentiment_logs)}")

        # Create employee scores
        for emp in employee_users:
            # Calculate avg sentiment from logs
            emp_logs = [l for l in sentiment_logs if l.employee_id == emp.id]
            if emp_logs:
                avg_score = sum(l.score for l in emp_logs) / len(emp_logs)
                min_score = min(l.score for l in emp_logs)
            else:
                avg_score = 50
                min_score = 50
            risk = max(0, min(100, int(100 - avg_score)))
            trend = "down" if min_score < 35 else "stable" if avg_score > 60 else "stable"
            delta = random.randint(-15, 10)

            score = EmployeeScore(
                employee_id=emp.id,
                sentiment_score=int(avg_score),
                engagement_score=int(avg_score),
                risk_score=risk,
                mental_health_score=int(avg_score),
                trend_delta=delta,
                trend_label=trend,
                last_updated=now,
            )
            db.add(score)
        db.flush()
        print(f"  Employee scores: {len(employee_users)}")

        # Create risk snapshots
        for emp in employee_users:
            emp_logs = [l for l in sentiment_logs if l.employee_id == emp.id]
            avg_score = sum(l.score for l in emp_logs) / len(emp_logs) if emp_logs else 50
            mood = avg_score
            attrition = max(0, min(1.0, (100 - avg_score) / 100))
            burnout = max(0, min(1.0, sum(1 for l in emp_logs if l.emotion in ("burnout", "exhaustion")) / max(len(emp_logs), 1)))
            snapshot = RiskSnapshot(
                id=uuid4(),
                user_id=emp.id,
                period_start=date.today() - timedelta(days=7),
                period_end=date.today(),
                engagement_score=float(avg_score),
                mood_score=float(mood),
                burnout_risk=float(burnout),
                attrition_risk=float(attrition),
                silence_risk=0.1,
                confidence=0.75,
                risk_reasons=["Recent sentiment patterns", "Workload indicators"],
                recommendations=["Schedule 1:1 check-in", "Review workload distribution"],
                created_at=now,
            )
            db.add(snapshot)
        db.flush()
        print(f"  Risk snapshots: {len(employee_users)}")

        # Create HR notifications (including sentiment alerts)
        alert_types = [
            ("sentiment_alert:sentiment_threshold", "Low sentiment detected", "Employee sentiment score dropped to 25/100", "high"),
            ("sentiment_alert:emotion_detected", "Burnout detected", "Employee expressed burnout in conversation", "critical"),
            ("sentiment_alert:sustained_negative", "Sustained negative sentiment", "Employee has shown 4 negative sentiments recently", "high"),
            ("sentiment_alert:conversation_risk", "High conversation risk", "Conversation risk score reached 85/100", "critical"),
            ("ticket_update", "New ticket raised", "Employee raised a hardware issue", "medium"),
            ("ticket_escalated", "Ticket escalated", "Complaint ticket was escalated to HR", "high"),
        ]
        for _ in range(8):
            emp = random.choice(employee_users)
            alert_type, title, body, severity = random.choice(alert_types)
            notif = HrNotification(
                id=uuid4(),
                ticket_id=None,
                actor_id=emp.id,
                title=title,
                body=body,
                notification_type=alert_type,
                severity=severity,
                created_at=now - timedelta(hours=random.randint(1, 72)),
            )
            db.add(notif)
        db.flush()
        print(f"  HR notifications: 8")

        # Create leave requests
        for emp in random.sample(employee_users, min(5, len(employee_users))):
            start = date.today() + timedelta(days=random.randint(5, 30))
            end = start + timedelta(days=random.randint(1, 5))
            lv = LeaveRequest(
                id=uuid4(),
                user_id=emp.id,
                leave_type=random.choice([LeaveType.annual, LeaveType.sick, LeaveType.personal]),
                start_date=start,
                end_date=end,
                reason="Personal time off",
                status=random.choice([LeaveStatus.pending, LeaveStatus.approved, LeaveStatus.approved]),
                created_at=now - timedelta(days=random.randint(1, 7)),
            )
            db.add(lv)
        db.flush()
        print(f"  Leave requests: 5")

        db.commit()
        print("\nDone! Demo data seeded successfully.")
        print(f"\nSign in:")
        print(f"  HR:        hr1@infeedo.ai         / {DEFAULT_PASSWORD}")
        print(f"  Manager:   manager1@infeedo.ai   / {DEFAULT_PASSWORD}")
        print(f"  Employee:  emp1@infeedo.ai       / {DEFAULT_PASSWORD}")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
