import logging
from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from ..models.ticket import Ticket, TicketStatus, TicketPriority, SLA_HOURS
from ..models.user import User, UserRole, UserStatus
from ..models.activity_event import ActivityEvent
from ..models.conversation import Conversation, Message, MessageSender
from ..models.reminder_schedule import ReminderSchedule
from ..models.automation_action import AutomationAction
from ..models.leave_request import LeaveRequest, LeaveStatus, LeaveType
from ..models.meeting_event import MeetingEvent
from ..models.hr_alert import HrAlert
from ..core.time import utcnow_naive
from ..database import SessionLocal

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

# Active event types for break detection
ACTIVE_EVENT_TYPES = {"chat_message", "typing", "work_session", "app_focus", "task_update"}
BREAK_EVENT_TYPES = {"break_taken", "away", "idle"}


def is_user_active(db: Session, user_id: UUID) -> bool:
    """Return True if the user has had activity in the last 30 minutes."""
    cutoff = utcnow_naive() - timedelta(minutes=30)
    try:
        recent = (
            db.query(ActivityEvent)
            .filter(
                ActivityEvent.user_id == user_id,
                ActivityEvent.event_at >= cutoff,
            )
            .first()
        )
        if recent is not None:
            return True
    except Exception:
        pass

    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user and getattr(user, "last_active_at", None) and user.last_active_at >= cutoff:
            return True
    except Exception:
        pass

    return False


def get_escalated_priority(current_priority: TicketPriority) -> TicketPriority:
    """Get the next priority level for escalation."""
    priority_order = [
        TicketPriority.low,
        TicketPriority.medium,
        TicketPriority.high,
        TicketPriority.critical
    ]
    
    try:
        current_idx = priority_order.index(current_priority)
        if current_idx < len(priority_order) - 1:
            return priority_order[current_idx + 1]
    except ValueError:
        pass
    
    return TicketPriority.high


def check_and_escalate_sla_breached_tickets() -> dict:
    db = SessionLocal()
    try:
        from .ticket import TicketService
        
        ticket_service = TicketService(db)
        
        open_statuses = [TicketStatus.open, TicketStatus.in_progress]
        tickets = (
            db.query(Ticket)
            .filter(Ticket.status.in_(open_statuses))
            .all()
        )
        
        escalated_count = 0
        escalated_tickets = []
        
        for ticket in tickets:
            if ticket_service.is_sla_breached(ticket):
                new_priority = get_escalated_priority(ticket.priority)
                old_priority = ticket.priority
                
                ticket.priority = new_priority
                ticket.status = TicketStatus.escalated
                
                escalation_msg = (
                    f"[AUTO-ESCALATED] SLA breached. "
                    f"Priority changed from {old_priority.value} to {new_priority.value}. "
                    f"Original SLA: {SLA_HOURS.get(old_priority, 24)} hours."
                )
                ticket_service.add_message(
                    ticket_id=ticket.id,
                    sender_id=None,
                    message_text=escalation_msg
                )
                
                escalated_tickets.append({
                    "ticket_id": str(ticket.id),
                    "old_priority": old_priority.value,
                    "new_priority": new_priority.value
                })
                escalated_count += 1
        
        db.commit()
        
        result = {
            "checked_at": utcnow_naive().isoformat(),
            "total_tickets_checked": len(tickets),
            "escalated_count": escalated_count,
            "escalated_tickets": escalated_tickets
        }
        
        logger.info(f"SLA check completed: {escalated_count}/{len(tickets)} tickets escalated")
        return result
        
    except Exception as e:
        logger.exception("SLA escalation job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def process_mark_due_reminders() -> dict:
    db = SessionLocal()
    try:
        from .mark_proactive import MarkProactiveService

        result = MarkProactiveService(db).process_due_reminders(batch_size=200)
        logger.info(
            "Reminder scheduler completed: processed=%s sent=%s",
            result.get("processed", 0),
            result.get("sent", 0),
        )
        return result
    except Exception as e:
        logger.exception("Reminder scheduler job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def check_lunch_reminder() -> dict:
    db = SessionLocal()
    try:
        now = utcnow_naive()
        lunch_hour = 13

        if now.hour < lunch_hour:
            return {"skipped": True, "reason": "before_lunch_time"}

        users = (
            db.query(User)
            .filter(User.role == UserRole.employee, User.status == UserStatus.active)
            .all()
        )

        sent_count = 0
        for user in users:
            if not is_user_active(db, user.id):
                continue

            existing = (
                db.query(AutomationAction)
                .filter(
                    AutomationAction.rule_name == "lunch_reminder",
                    AutomationAction.user_id == user.id,
                    AutomationAction.executed_at >= now - timedelta(hours=1, minutes=30),
                )
                .first()
            )
            if existing:
                continue

            db.add(
                AutomationAction(
                    rule_name="lunch_reminder",
                    user_id=user.id,
                    target_type="user",
                    action_type="nudge",
                    status="sent",
                    executed_at=now,
                )
            )
            sent_count += 1

        db.commit()
        logger.info(f"Lunch reminder job completed: sent={sent_count}")
        return {"sent": sent_count, "checked_at": now.isoformat()}

    except Exception as e:
        logger.exception("Lunch reminder job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def check_break_reminder() -> dict:
    db = SessionLocal()
    try:
        now = utcnow_naive()
        window_start = now - timedelta(hours=2, minutes=30)

        users = (
            db.query(User)
            .filter(User.role == UserRole.employee, User.status == UserStatus.active)
            .all()
        )

        sent_count = 0
        for user in users:
            if not is_user_active(db, user.id):
                continue

            active_count = (
                db.query(func.count(ActivityEvent.id))
                .filter(
                    ActivityEvent.user_id == user.id,
                    ActivityEvent.event_at >= window_start,
                    ActivityEvent.event_type.in_(ACTIVE_EVENT_TYPES),
                )
                .scalar()
                or 0
            )

            break_count = (
                db.query(func.count(ActivityEvent.id))
                .filter(
                    ActivityEvent.user_id == user.id,
                    ActivityEvent.event_at >= window_start,
                    ActivityEvent.event_type.in_(BREAK_EVENT_TYPES),
                )
                .scalar()
                or 0
            )

            if active_count >= 6 and break_count == 0:
                existing = (
                    db.query(AutomationAction)
                    .filter(
                        AutomationAction.rule_name == "break_reminder",
                        AutomationAction.user_id == user.id,
                        AutomationAction.created_at >= now - timedelta(hours=1),
                    )
                    .first()
                )
                if existing:
                    continue

                db.add(
                    AutomationAction(
                        rule_name="break_reminder",
                        user_id=user.id,
                        target_type="user",
                        action_type="nudge",
                        status="sent",
                        executed_at=now,
                        trigger_context={"active_count": active_count},
                    )
                )
                sent_count += 1

        db.commit()
        logger.info(f"Break reminder job completed: sent={sent_count}")
        return {"sent": sent_count, "checked_at": now.isoformat()}

    except Exception as e:
        logger.exception("Break reminder job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def check_health_followup() -> dict:
    db = SessionLocal()
    try:
        from .proactive_triggers import ProactiveTriggerService

        now = utcnow_naive()
        window_start = now - timedelta(hours=4)

        pending = (
            db.query(ReminderSchedule)
            .filter(
                ReminderSchedule.reminder_type == "health_followup",
                ReminderSchedule.status == "active",
                ReminderSchedule.next_trigger_at.isnot(None),
                ReminderSchedule.next_trigger_at <= now,
            )
            .all()
        )

        processed = 0
        for schedule in pending:
            service = ProactiveTriggerService(db)
            if not service.can_send_proactive(schedule.user_id):
                schedule.status = "cancelled"
                schedule.next_trigger_at = None
                continue

            db.add(
                AutomationAction(
                    rule_name="health_followup",
                    user_id=schedule.user_id,
                    target_type="user",
                    action_type="reminder",
                    status="sent",
                    executed_at=now,
                    trigger_context={
                        "reminder_id": str(schedule.id),
                        "title": schedule.title,
                    },
                )
            )

            schedule.last_triggered_at = now
            schedule.status = "cancelled"
            schedule.next_trigger_at = None
            processed += 1

        db.commit()
        logger.info(f"Health follow-up job completed: processed={processed}")
        return {"processed": processed, "checked_at": now.isoformat()}

    except Exception as e:
        logger.exception("Health follow-up job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def check_silent_users() -> dict:
    db = SessionLocal()
    try:
        from .proactive_triggers import ProactiveTriggerService

        now = utcnow_naive()
        silence_threshold = now - timedelta(days=3)

        users = (
            db.query(User)
            .filter(User.role == UserRole.employee, User.status == UserStatus.active)
            .all()
        )

        sent_count = 0
        silent_users = []
        for user in users:
            if not is_user_active(db, user.id):
                continue

            last_message = (
                db.query(func.max(Message.created_at))
                .join(Conversation, Message.conversation_id == Conversation.id)
                .filter(Conversation.user_id == user.id, Message.sender == MessageSender.user)
                .scalar()
            )

            if last_message is None or last_message < silence_threshold:
                silent_users.append(user)

                existing = (
                    db.query(AutomationAction)
                    .filter(
                        AutomationAction.rule_name == "silent_user_followup",
                        AutomationAction.user_id == user.id,
                        AutomationAction.executed_at >= now - timedelta(hours=24),
                    )
                    .first()
                )
                if existing:
                    continue

                service = ProactiveTriggerService(db)
                if not service.can_send_proactive(user.id):
                    continue

                db.add(
                    AutomationAction(
                        rule_name="silent_user_followup",
                        user_id=user.id,
                        target_type="user",
                        action_type="followup",
                        status="sent",
                        executed_at=now,
                        trigger_context={"last_message": last_message.isoformat() if last_message else None},
                    )
                )

                db.add(
                    ReminderSchedule(
                        user_id=user.id,
                        reminder_type="silent_user",
                        title="Just checking in",
                        message="Haven't heard from you in a while – everything okay?",
                        schedule_kind="one_time",
                        run_at=now,
                        timezone="UTC",
                        status="active",
                        next_trigger_at=now,
                    )
                )
                sent_count += 1

        db.commit()
        logger.info(f"Silent users job completed: silent={len(silent_users)}, sent={sent_count}")
        return {"silent_users": len(silent_users), "sent": sent_count, "checked_at": now.isoformat()}

    except Exception as e:
        logger.exception("Silent users job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def check_mental_health_alerts() -> dict:
    db = SessionLocal()
    try:
        from .mental_health import calculate_mental_health, create_risk_alert

        now = utcnow_naive()
        window_start = now - timedelta(hours=4)

        users = (
            db.query(User)
            .filter(User.role == UserRole.employee, User.status == UserStatus.active)
            .all()
        )

        alerts_created = 0
        checked_users = 0

        for user in users:
            if not is_user_active(db, user.id):
                continue

            existing = (
                db.query(AutomationAction)
                .filter(
                    AutomationAction.rule_name == "mental_health_alert",
                    AutomationAction.user_id == user.id,
                    AutomationAction.executed_at >= window_start,
                )
                .first()
            )
            if existing:
                continue

            result = calculate_mental_health(db, user.id, days=30)
            mental_health = result["mental_health"]
            sentiment = result["sentiment"]

            if mental_health < 40 or sentiment < 40:
                severity = "critical" if mental_health < 20 else "high"
                alert_type = (
                    "mental_health_critical"
                    if mental_health < 20
                    else "mental_health_at_risk"
                )
                alert = create_risk_alert(
                    db=db,
                    user_id=user.id,
                    alert_type=alert_type,
                    severity=severity,
                )
                if alert:
                    alerts_created += 1
            checked_users += 1

        logger.info(f"Mental health alert job completed: checked={checked_users}, alerts={alerts_created}")
        return {"checked_users": checked_users, "alerts_created": alerts_created, "checked_at": now.isoformat()}

    except Exception as e:
        logger.exception("Mental health alert job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def check_pto_nudges() -> dict:
    """Check for employees who haven't taken leave in 60+ days and send nudges."""
    db = SessionLocal()
    try:
        from .proactive_triggers import ProactiveTriggerService

        now = utcnow_naive()
        days_threshold = 60
        threshold_date = now.date() - timedelta(days=days_threshold)

        users = (
            db.query(User)
            .filter(User.role == UserRole.employee, User.status == UserStatus.active)
            .all()
        )

        sent_count = 0
        for user in users:
            last_leave = (
                db.query(func.max(LeaveRequest.end_date))
                .filter(
                    LeaveRequest.user_id == user.id,
                    LeaveRequest.status == LeaveStatus.approved,
                    LeaveRequest.end_date < threshold_date,
                )
                .scalar()
            )

            if last_leave is None:
                last_leave = (
                    db.query(func.max(LeaveRequest.end_date))
                    .filter(
                        LeaveRequest.user_id == user.id,
                        LeaveRequest.end_date < threshold_date,
                    )
                    .scalar()
                )

            if last_leave is None:
                last_leave = (
                    db.query(func.max(LeaveRequest.created_at))
                    .filter(LeaveRequest.user_id == user.id)
                    .scalar()
                )
                if last_leave:
                    last_leave = last_leave.date()

            if last_leave is not None and last_leave >= threshold_date:
                continue

            existing = (
                db.query(AutomationAction)
                .filter(
                    AutomationAction.rule_name == "pto_nudge",
                    AutomationAction.user_id == user.id,
                    AutomationAction.executed_at >= now - timedelta(days=7),
                )
                .first()
            )
            if existing:
                continue

            service = ProactiveTriggerService(db)
            if not service.can_send_proactive(user.id):
                continue

            db.add(
                AutomationAction(
                    rule_name="pto_nudge",
                    user_id=user.id,
                    target_type="user",
                    action_type="nudge",
                    status="sent",
                    executed_at=now,
                    trigger_context={
                        "last_leave": last_leave.isoformat() if last_leave else None,
                        "days_ago": (now.date() - last_leave).days if last_leave else None,
                    },
                )
            )

            db.add(
                ReminderSchedule(
                    user_id=user.id,
                    reminder_type="pto_reminder",
                    title="Time for a break?",
                    message="You haven't taken PTO in a while. Consider planning some time off to recharge!",
                    schedule_kind="one_time",
                    run_at=now,
                    timezone="UTC",
                    status="active",
                    next_trigger_at=now,
                )
            )
            sent_count += 1

        db.commit()
        logger.info(f"PTO nudge job completed: sent={sent_count}")
        return {"sent": sent_count, "checked_at": now.isoformat()}

    except Exception as e:
        logger.exception("PTO nudge job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def track_meeting(
    user_id: UUID,
    meeting_title: str = None,
    meeting_id: str = None,
    duration_minutes: int = None,
    meeting_at: datetime = None,
) -> dict:
    """Track a meeting event for a user."""
    db = SessionLocal()
    try:
        now = utcnow_naive()
        if meeting_at is None:
            meeting_at = now

        meeting = MeetingEvent(
            user_id=user_id,
            meeting_title=meeting_title,
            meeting_id=meeting_id,
            duration_minutes=duration_minutes,
            meeting_at=meeting_at,
        )
        db.add(meeting)
        db.commit()

        logger.info(f"Meeting tracked for user {user_id}: {meeting_title}")
        return {"tracked": True, "meeting_id": str(meeting.id)}

    except Exception as e:
        logger.exception("Failed to track meeting")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def check_meeting_fatigue() -> dict:
    """Check for meeting fatigue - users with 5+ meetings in a day get alerted."""
    db = SessionLocal()
    try:
        from .proactive_triggers import ProactiveTriggerService

        now = utcnow_naive()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        MEETING_FATIGUE_THRESHOLD = 5

        users = (
            db.query(User)
            .filter(User.role == UserRole.employee, User.status == UserStatus.active)
            .all()
        )

        alerts_sent = 0
        checked_users = 0

        for user in users:
            meeting_count = (
                db.query(func.count(MeetingEvent.id))
                .filter(
                    MeetingEvent.user_id == user.id,
                    MeetingEvent.meeting_at >= today_start,
                )
                .scalar()
                or 0
            )

            if meeting_count < MEETING_FATIGUE_THRESHOLD:
                continue

            checked_users += 1

            existing = (
                db.query(AutomationAction)
                .filter(
                    AutomationAction.rule_name == "meeting_fatigue_alert",
                    AutomationAction.user_id == user.id,
                    AutomationAction.executed_at >= now - timedelta(hours=12),
                )
                .first()
            )
            if existing:
                continue

            service = ProactiveTriggerService(db)
            if not service.can_send_proactive(user.id):
                continue

            total_duration = (
                db.query(func.sum(MeetingEvent.duration_minutes))
                .filter(
                    MeetingEvent.user_id == user.id,
                    MeetingEvent.meeting_at >= today_start,
                )
                .scalar()
                or 0
            )

            db.add(
                AutomationAction(
                    rule_name="meeting_fatigue_alert",
                    user_id=user.id,
                    target_type="user",
                    action_type="alert",
                    status="sent",
                    executed_at=now,
                    trigger_context={
                        "meeting_count": meeting_count,
                        "total_duration_minutes": total_duration,
                    },
                )
            )

            db.add(
                ReminderSchedule(
                    user_id=user.id,
                    reminder_type="meeting_fatigue",
                    title="Meeting overload detected",
                    message=f"You have {meeting_count} meetings today ({total_duration} min total). Consider blocking some focus time.",
                    schedule_kind="one_time",
                    run_at=now,
                    timezone="UTC",
                    status="active",
                    next_trigger_at=now,
                )
            )
            alerts_sent += 1

        db.commit()
        logger.info(f"Meeting fatigue check completed: checked={checked_users}, alerts={alerts_sent}")
        return {"checked_users": checked_users, "alerts_sent": alerts_sent, "checked_at": now.isoformat()}

    except Exception as e:
        logger.exception("Meeting fatigue check failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def check_wellness_nudges() -> dict:
    """Check for users who need wellness nudges (stretch, hydration, eye breaks)."""
    db = SessionLocal()
    try:
        from .proactive_triggers import ProactiveTriggerService

        now = utcnow_naive()
        
        # Only trigger at appropriate times: 10:30 AM (mid-morning stretch) 
        # and 2:30 PM (afternoon hydration/eye break)
        WELLNESS_TRIGGER_HOURS = [10, 14]
        
        if now.hour not in WELLNESS_TRIGGER_HOURS:
            return {"skipped": True, "reason": "not_trigger_hour"}
        
        # Also only trigger within first 30 min of the hour
        if now.minute > 30:
            return {"skipped": True, "reason": "outside_trigger_window"}

        # Get active wellness tips
        from ..models.wellness_tip import WellnessTip
        tips = db.query(WellnessTip).filter(WellnessTip.is_active == True).all()
        
        if not tips:
            return {"skipped": True, "reason": "no_active_tips"}

        users = (
            db.query(User)
            .filter(User.role == UserRole.employee, User.status == UserStatus.active)
            .all()
        )

        sent_count = 0
        for user in users:
            if not is_user_active(db, user.id):
                continue

            # Check if we already sent a wellness nudge recently (last 4 hours)
            existing = (
                db.query(AutomationAction)
                .filter(
                    AutomationAction.rule_name == "wellness_nudge",
                    AutomationAction.user_id == user.id,
                    AutomationAction.executed_at >= now - timedelta(hours=4),
                )
                .first()
            )
            if existing:
                continue

            service = ProactiveTriggerService(db)
            if not service.can_send_proactive(user.id):
                continue

            # Select a random wellness tip
            import random
            tip = random.choice(tips)

            db.add(
                AutomationAction(
                    rule_name="wellness_nudge",
                    user_id=user.id,
                    target_type="user",
                    action_type="nudge",
                    status="sent",
                    executed_at=now,
                    trigger_context={
                        "tip_type": tip.tip_type.value,
                        "tip_title": tip.title,
                    },
                )
            )

            db.add(
                ReminderSchedule(
                    user_id=user.id,
                    reminder_type="wellness_nudge",
                    title=tip.title,
                    message=tip.content,
                    schedule_kind="one_time",
                    run_at=now,
                    timezone="UTC",
                    status="active",
                    next_trigger_at=now,
                )
            )
            sent_count += 1

        db.commit()
        logger.info(f"Wellness nudge job completed: sent={sent_count}")
        return {"sent": sent_count, "checked_at": now.isoformat()}

    except Exception as e:
        logger.exception("Wellness nudge job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def check_repeated_complaints() -> dict:
    db = SessionLocal()
    try:
        now = utcnow_naive()
        window_start = now - timedelta(days=7)

        rows = (
            db.query(Ticket.user_id, func.count(Ticket.id).label("count"))
            .filter(Ticket.category == "complaint", Ticket.created_at >= window_start)
            .group_by(Ticket.user_id)
            .having(func.count(Ticket.id) >= 2)
            .all()
        )

        escalated_count = 0
        for user_id, count in rows:
            if not is_user_active(db, user_id):
                continue

            latest_ticket = (
                db.query(Ticket)
                .filter(
                    Ticket.user_id == user_id,
                    Ticket.category == "complaint",
                    Ticket.created_at >= window_start,
                )
                .order_by(Ticket.created_at.desc())
                .first()
            )
            if not latest_ticket:
                continue

            if latest_ticket.priority not in (
                TicketPriority.high,
                TicketPriority.critical,
            ):
                latest_ticket.priority = TicketPriority.high
                latest_ticket.status = TicketStatus.escalated

            alert = HrAlert(
                title="Repeated complaints detected",
                body=(
                    f"User {user_id} has {count} complaint tickets in the last 7 days. "
                    f"Latest ticket ({latest_ticket.id}) escalated to HIGH."
                ),
                severity="high",
                alert_type="repeated_complaints",
                source="scheduler",
            )
            db.add(alert)

            db.add(
                AutomationAction(
                    rule_name="repeated_complaints",
                    user_id=user_id,
                    target_type="hr",
                    action_type="hr_alert",
                    status="sent",
                    executed_at=now,
                    trigger_context={
                        "ticket_id": str(latest_ticket.id),
                        "complaint_count": count,
                    },
                )
            )
            escalated_count += 1

        db.commit()
        logger.info(f"Repeated complaints job completed: escalated={escalated_count}")
        return {"escalated": escalated_count, "checked_at": now.isoformat()}

    except Exception as e:
        logger.exception("Repeated complaints job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


ONBOARDING_MILESTONES = {
    1: "How's your first day going? 😊 If anything's unclear, I'm right here — and a quick line of feedback helps us make onboarding better.",
    7: "One week in! 🎉 How are you settling in? Mind sharing a little feedback on your first week?",
    30: "A whole month already! 🌟 How's it been so far? Your honest feedback shapes how we support new folks.",
}


def _survey_link(survey_id: str) -> str:
    return f"/surveys?survey={survey_id}"


def check_onboarding_surveys() -> dict:
    """Nudge employees at onboarding milestones (day 1 / 7 / 30).

    Uses ``User.created_at`` as the hire-date proxy (no dedicated hire_date
    column exists). Points at the canonical onboarding survey so the response
    is structured. Delivered as an active one-time reminder so it rides the
    existing dispatch + live-SSE path. Deduped per user per milestone.
    """
    db = SessionLocal()
    try:
        from .lifecycle_surveys import ensure_lifecycle_surveys, get_lifecycle_survey

        now = utcnow_naive()
        today = now.date()
        users = (
            db.query(User)
            .filter(User.role == UserRole.employee, User.status == UserStatus.active)
            .all()
        )

        survey = get_lifecycle_survey(db, "onboarding")
        if survey is None:
            ensure_lifecycle_surveys(db)
            survey = get_lifecycle_survey(db, "onboarding")
        survey_id = str(survey.id) if survey else None

        sent = 0
        for user in users:
            created = getattr(user, "created_at", None)
            if created is None:
                continue
            days_since = (today - created.date()).days
            if days_since not in ONBOARDING_MILESTONES:
                continue

            rule_name = f"onboarding_survey_d{days_since}"
            existing = (
                db.query(AutomationAction)
                .filter(
                    AutomationAction.rule_name == rule_name,
                    AutomationAction.user_id == user.id,
                )
                .first()
            )
            if existing:
                continue

            message = ONBOARDING_MILESTONES[days_since]
            payload = {}
            if survey_id:
                message = f"{message}\n\nShare your feedback here: {_survey_link(survey_id)}"
                payload = {"survey_id": survey_id, "action_url": _survey_link(survey_id)}

            db.add(
                AutomationAction(
                    rule_name=rule_name,
                    user_id=user.id,
                    target_type="user",
                    action_type="nudge",
                    status="sent",
                    executed_at=now,
                    trigger_context={"milestone_day": days_since, "survey_id": survey_id},
                )
            )
            db.add(
                ReminderSchedule(
                    user_id=user.id,
                    reminder_type="onboarding_survey",
                    title=f"Onboarding check-in (day {days_since})",
                    message=message,
                    schedule_kind="one_time",
                    run_at=now,
                    timezone="UTC",
                    status="active",
                    next_trigger_at=now,
                    payload=payload,
                )
            )
            sent += 1

        db.commit()
        logger.info(f"Onboarding survey job completed: sent={sent}")
        return {"sent": sent, "checked_at": now.isoformat()}
    except Exception as e:
        logger.exception("Onboarding survey job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def check_exit_surveys() -> dict:
    """Invite a departing employee to an exit check-in around their last day.

    Fires once when ``departure_at`` is within the next 2 days (or already
    passed but within the last 2 days), deduped per user. Uses the same
    deliver-live reminder path as onboarding.
    """
    db = SessionLocal()
    try:
        now = utcnow_naive()
        window_start = now - timedelta(days=2)
        window_end = now + timedelta(days=2)
        users = (
            db.query(User)
            .filter(
                User.role == UserRole.employee,
                User.departure_at.isnot(None),
                User.departure_at >= window_start,
                User.departure_at <= window_end,
            )
            .all()
        )

        from .lifecycle_surveys import ensure_lifecycle_surveys, get_lifecycle_survey

        survey = get_lifecycle_survey(db, "exit")
        if survey is None:
            ensure_lifecycle_surveys(db)
            survey = get_lifecycle_survey(db, "exit")
        survey_id = str(survey.id) if survey else None

        sent = 0
        for user in users:
            existing = (
                db.query(AutomationAction)
                .filter(
                    AutomationAction.rule_name == "exit_survey",
                    AutomationAction.user_id == user.id,
                )
                .first()
            )
            if existing:
                continue

            message = (
                "As you wrap up here, I'd love a few honest words about your "
                "experience — what worked, what didn't. It genuinely helps the "
                "folks who come after you. 💙"
            )
            payload = {}
            if survey_id:
                message = f"{message}\n\nShare your reflections here: {_survey_link(survey_id)}"
                payload = {"survey_id": survey_id, "action_url": _survey_link(survey_id)}

            db.add(
                AutomationAction(
                    rule_name="exit_survey",
                    user_id=user.id,
                    target_type="user",
                    action_type="nudge",
                    status="sent",
                    executed_at=now,
                    trigger_context={"departure_at": user.departure_at.isoformat(), "survey_id": survey_id},
                )
            )
            db.add(
                ReminderSchedule(
                    user_id=user.id,
                    reminder_type="exit_survey",
                    title="Before you go",
                    message=message,
                    schedule_kind="one_time",
                    run_at=now,
                    timezone="UTC",
                    status="active",
                    next_trigger_at=now,
                    payload=payload,
                )
            )
            sent += 1

        db.commit()
        logger.info(f"Exit survey job completed: sent={sent}")
        return {"sent": sent, "checked_at": now.isoformat()}
    except Exception as e:
        logger.exception("Exit survey job failed")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def start_scheduler():
    if scheduler.running:
        logger.warning("Scheduler already running")
        return

    scheduler.add_job(
        check_and_escalate_sla_breached_tickets,
        trigger=IntervalTrigger(hours=1),
        id="sla_escalation_job",
        name="SLA Auto-Escalation",
        replace_existing=True
    )

    scheduler.add_job(
        process_mark_due_reminders,
        trigger=IntervalTrigger(minutes=15),
        id="mark_reminder_job",
        name="MARK Reminder Dispatch",
        replace_existing=True
    )

    scheduler.add_job(
        check_lunch_reminder,
        trigger=IntervalTrigger(hours=1),
        id="lunch_reminder_job",
        name="Lunch Reminder",
        replace_existing=True
    )

    scheduler.add_job(
        check_break_reminder,
        trigger=IntervalTrigger(minutes=30),
        id="break_reminder_job",
        name="Break Reminder",
        replace_existing=True
    )

    scheduler.add_job(
        check_health_followup,
        trigger=IntervalTrigger(minutes=15),
        id="health_followup_job",
        name="Health Follow-up",
        replace_existing=True
    )

    scheduler.add_job(
        check_silent_users,
        trigger=IntervalTrigger(hours=1),
        id="silent_users_job",
        name="Silent Users Detection",
        replace_existing=True
    )

    scheduler.add_job(
        check_mental_health_alerts,
        trigger=IntervalTrigger(hours=1),
        id="mental_health_alert_job",
        name="Mental Health Alert Check",
        replace_existing=True
    )

    scheduler.add_job(
        check_pto_nudges,
        trigger=IntervalTrigger(hours=1),
        id="pto_nudge_job",
        name="PTO Nudge",
        replace_existing=True
    )

    scheduler.add_job(
        check_meeting_fatigue,
        trigger=IntervalTrigger(hours=1),
        id="meeting_fatigue_job",
        name="Meeting Fatigue Check",
        replace_existing=True
    )

    scheduler.add_job(
        check_wellness_nudges,
        trigger=IntervalTrigger(hours=1),
        id="wellness_nudge_job",
        name="Wellness Nudge",
        replace_existing=True
    )

    scheduler.add_job(
        check_repeated_complaints,
        trigger=IntervalTrigger(hours=1),
        id="repeated_complaints_job",
        name="Repeated Complaints Check",
        replace_existing=True
    )

    scheduler.add_job(
        check_onboarding_surveys,
        trigger=IntervalTrigger(hours=24),
        id="onboarding_survey_job",
        name="Onboarding Survey Nudges",
        replace_existing=True
    )

    scheduler.add_job(
        check_exit_surveys,
        trigger=IntervalTrigger(hours=24),
        id="exit_survey_job",
        name="Exit Survey Nudges",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Background scheduler started with SLA, MARK reminder, lunch, break, health follow-up, silent users, mental health, meeting fatigue, wellness nudge, and repeated complaints jobs")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler stopped")
