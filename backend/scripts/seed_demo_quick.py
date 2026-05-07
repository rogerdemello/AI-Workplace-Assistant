import sys
from pathlib import Path
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import app.models
from app.database import SessionLocal
from app.auth.password import hash_password
from app.models.department import Department
from app.models.user import User, UserRole, UserStatus
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.conversation import Conversation, Message, MessageSender
from app.models.sentiment_log import SentimentLog
from app.models.employee_score import EmployeeScore
from app.models.risk_snapshot import RiskSnapshot
from app.models.hr_notification import HrNotification
from app.models.leave_request import LeaveRequest, LeaveStatus, LeaveType
from app.core.time import utcnow_naive
from datetime import timedelta, date
from uuid import uuid4
import random

db = SessionLocal()
try:
    depts = []
    for name, desc in [("Engineering", "Product engineering"), ("People Ops", "HR"), ("Sales", "Revenue"), ("Design", "UX")]:
        d = db.query(Department).filter(Department.name == name).first()
        if not d:
            d = Department(name=name, description=desc)
            db.add(d)
            db.flush()
        depts.append(d)

    users_data = [
        ("hr_demo@infeedo.ai", "HR Demo", "HR-DMO-26", UserRole.hr, 1, None),
        ("mgr_eng@infeedo.ai", "Alice Chen", "MGR-ENG-26", UserRole.manager, 0, None),
        ("mgr_sales@infeedo.ai", "Bob Patel", "MGR-SAL-26", UserRole.manager, 2, None),
        ("emp1@infeedo.ai", "Carol Williams", "EMP-59R0X0", UserRole.employee, 0, 1),
        ("emp2@infeedo.ai", "David Kim", "EMP-YRD6N3", UserRole.employee, 0, 1),
        ("emp3@infeedo.ai", "Eva Martinez", "EMP-OHY82D", UserRole.employee, 0, 1),
        ("emp4@infeedo.ai", "Frank Liu", "EMP-OKJBU5", UserRole.employee, 0, 1),
        ("emp5@infeedo.ai", "Grace Okafor", "EMP-BAN66W", UserRole.employee, 2, 2),
        ("emp6@infeedo.ai", "Hassan Ali", "EMP-E4SOMH", UserRole.employee, 2, 2),
        ("emp7@infeedo.ai", "Ivan Petrov", "EMP-ZWJ4GB", UserRole.employee, 3, None),
        ("emp8@infeedo.ai", "Julia Schmidt", "EMP-PEQ0WZ", UserRole.employee, 3, None),
    ]
    users = []
    user_map = {}
    for i, (email, name, eid, role, dept_idx, mgr_idx) in enumerate(users_data):
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            user = existing
        else:
            mgr_id = user_map.get(mgr_idx) if mgr_idx is not None else None
            user = User(
                id=uuid4(), email=email, name=name, employee_id=eid,
                hashed_password=hash_password("password123"), role=role,
                designation="Team Member", status=UserStatus.active,
                department_id=depts[dept_idx].id if dept_idx < len(depts) else None,
                manager_id=mgr_id,
            )
            db.add(user)
            db.flush()
        users.append(user)
        user_map[i] = user.id
        print(f"User: {name}")

    hr_user = users[0]
    emp_users = [u for u in users if u.role == UserRole.employee]

    now = utcnow_naive()
    tickets_data = [
        ("Laptop screen flickering", "hardware", TicketPriority.high, TicketStatus.open),
        ("Request ergonomic chair", "facilities", TicketPriority.medium, TicketStatus.in_progress),
        ("Payroll discrepancy March", "payroll", TicketPriority.high, TicketStatus.open),
        ("Team lead behavior concern", "complaint", TicketPriority.critical, TicketStatus.escalated),
        ("Staging access needed", "access", TicketPriority.medium, TicketStatus.resolved),
        ("Vacation approval pending", "leave", TicketPriority.low, TicketStatus.open),
        ("Harassment report", "complaint", TicketPriority.critical, TicketStatus.escalated),
        ("Insurance dependents missing", "benefits", TicketPriority.medium, TicketStatus.in_progress),
        ("VPN disconnecting", "it_support", TicketPriority.medium, TicketStatus.open),
        ("Training budget request", "learning", TicketPriority.low, TicketStatus.resolved),
        ("Overwhelmed with workload", "wellbeing", TicketPriority.high, TicketStatus.open),
        ("Team conflict", "complaint", TicketPriority.high, TicketStatus.in_progress),
    ]
    for title, cat, prio, status in tickets_data:
        user = random.choice(emp_users)
        created = now - timedelta(hours=random.randint(1, 168))
        resolved = created + timedelta(hours=random.randint(2, 48)) if status == TicketStatus.resolved else None
        t = Ticket(
            id=uuid4(), user_id=user.id, query=title, category=cat, status=status,
            priority=prio, assigned_to=hr_user.id if status != TicketStatus.open else None,
            created_at=created, updated_at=resolved or created, resolved_at=resolved,
            sentiment_score=random.randint(20, 85),
        )
        db.add(t)
    db.flush()
    print(f"Tickets: {len(tickets_data)}")

    sentiment_msgs = [
        ("Really happy with new project!", "positive", "satisfaction", 82),
        ("Workload is too much", "negative", "overwhelm", 22),
        ("Great team lunch today", "positive", "joy", 78),
        ("Feeling burnt out", "negative", "burnout", 15),
        ("Not sure about policy changes", "neutral", "confusion", 48),
        ("Frustrated with slow approvals", "negative", "frustration", 28),
        ("Manager very supportive", "positive", "gratitude", 85),
        ("Anxious about deadline", "negative", "anxiety", 32),
        ("Everything is fine", "neutral", "neutral", 55),
        ("Extremely stressed", "negative", "panic", 12),
        ("Love remote flexibility", "positive", "satisfaction", 80),
        ("Feeling isolated", "negative", "loneliness", 35),
    ]

    logs = []
    for emp in emp_users:
        for _ in range(random.randint(1, 3)):
            conv = Conversation(
                id=uuid4(), user_id=emp.id, status="active",
                started_at=now - timedelta(days=random.randint(1, 14), hours=random.randint(0, 23)),
            )
            db.add(conv)
            db.flush()
            for mi in range(random.randint(2, 6)):
                txt, lbl, emo, score = random.choice(sentiment_msgs)
                msg = Message(
                    id=uuid4(), conversation_id=conv.id,
                    sender=MessageSender.user if mi % 2 == 0 else MessageSender.bot,
                    message_text=txt,
                    created_at=conv.started_at + timedelta(minutes=mi * 5),
                )
                db.add(msg)
                db.flush()
                if msg.sender == MessageSender.user:
                    log = SentimentLog(
                        id=uuid4(), employee_id=emp.id, conversation_id=conv.id,
                        message_id=msg.id, score=score, label=lbl, emotion=emo,
                        analysis_source=random.choice(["llm", "hybrid", "lexicon"]),
                        created_at=msg.created_at,
                    )
                    db.add(log)
                    logs.append(log)
    db.flush()
    print(f"Sentiment logs: {len(logs)}")

    for emp in emp_users:
        emp_logs = [l for l in logs if l.employee_id == emp.id]
        avg = sum(l.score for l in emp_logs) / len(emp_logs) if emp_logs else 50
        risk = max(0, min(100, int(100 - avg)))
        es = EmployeeScore(
            employee_id=emp.id, sentiment_score=int(avg), engagement_score=int(avg),
            risk_score=risk, mental_health_score=int(avg),
            trend_delta=random.randint(-15, 10), trend_label="stable", last_updated=now,
        )
        db.add(es)
    db.flush()
    print("Employee scores created")

    for emp in emp_users:
        emp_logs = [l for l in logs if l.employee_id == emp.id]
        avg = sum(l.score for l in emp_logs) / len(emp_logs) if emp_logs else 50
        attrition = max(0, min(1.0, (100 - avg) / 100))
        burnout = max(0, min(1.0, sum(1 for l in emp_logs if l.emotion in ("burnout", "exhaustion")) / max(len(emp_logs), 1)))
        rs = RiskSnapshot(
            id=uuid4(), user_id=emp.id,
            period_start=date.today() - timedelta(days=7),
            period_end=date.today(),
            engagement_score=float(avg), mood_score=float(avg),
            burnout_risk=float(burnout), attrition_risk=float(attrition),
            silence_risk=0.1, confidence=0.75,
            risk_reasons=["Recent sentiment patterns"],
            recommendations=["Schedule 1:1 check-in"],
            created_at=now,
        )
        db.add(rs)
    db.flush()
    print("Risk snapshots created")

    alerts = [
        ("sentiment_alert:sentiment_threshold", "Low sentiment detected", "Score dropped to 25/100", "high"),
        ("sentiment_alert:emotion_detected", "Burnout detected", "Expressed burnout", "critical"),
        ("sentiment_alert:sustained_negative", "Sustained negative", "4 negative signals", "high"),
        ("sentiment_alert:conversation_risk", "High conversation risk", "Risk 85/100", "critical"),
        ("ticket_update", "New ticket raised", "Hardware issue", "medium"),
        ("ticket_escalated", "Ticket escalated", "Complaint escalated", "high"),
    ]
    for _ in range(8):
        emp = random.choice(emp_users)
        atype, title, body, sev = random.choice(alerts)
        n = HrNotification(
            id=uuid4(), ticket_id=None, actor_id=emp.id, title=title,
            body=body, notification_type=atype, severity=sev,
            created_at=now - timedelta(hours=random.randint(1, 72)),
        )
        db.add(n)
    db.flush()
    print("HR notifications created")

    for emp in random.sample(emp_users, min(5, len(emp_users))):
        start = date.today() + timedelta(days=random.randint(5, 30))
        end = start + timedelta(days=random.randint(1, 5))
        lv = LeaveRequest(
            id=uuid4(), user_id=emp.id,
            leave_type=random.choice([LeaveType.paid, LeaveType.sick, LeaveType.work_from_home]),
            start_date=start, end_date=end, reason="Personal time off",
            status=random.choice([LeaveStatus.pending, LeaveStatus.approved, LeaveStatus.approved]),
            created_at=now - timedelta(days=random.randint(1, 7)),
        )
        db.add(lv)
    db.flush()
    print("Leave requests created")

    db.commit()
    print("\nDone! Demo data committed.")
    print("Login: hr_demo@infeedo.ai / password123")
except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
