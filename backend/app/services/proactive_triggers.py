"""
Proactive Trigger Service - Schedules follow-up actions based on detected events.

This module provides proactive trigger scheduling for:
- health_followup: When health concerns are detected
- checkin: Scheduled check-ins
- break_reminder: Break reminders after active sessions
- silent_user: Follow-up for users who are quiet

Uses ReminderSchedule for storage with cooldown prevention.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..core.time import utcnow_naive
from ..models.reminder_schedule import ReminderSchedule

# Valid trigger types
VALID_TRIGGER_TYPES = {
    "health_followup",
    "checkin",
    "break_reminder",
    "silent_user",
}

# Default cooldown window in hours
DEFAULT_COOLDOWN_HOURS = 2


class ProactiveTriggerService:
    """Service for managing proactive triggers with cooldown."""

    def __init__(self, db: Session):
        self.db = db
        self._cooldown_hours = DEFAULT_COOLDOWN_HOURS

    def is_cooldown_active(self, user_id: UUID) -> bool:
        """
        Check if a proactive trigger was sent within the cooldown window.

        Args:
            user_id: The user ID to check.

        Returns:
            True if cooldown is active (recent trigger exists), False otherwise.
        """
        now = utcnow_naive()
        window_start = now - timedelta(hours=self._cooldown_hours)

        recent_trigger = (
            self.db.query(ReminderSchedule)
            .filter(
                ReminderSchedule.user_id == user_id,
                ReminderSchedule.status == "active",
                ReminderSchedule.schedule_kind == "one_time",
                ReminderSchedule.next_trigger_at.isnot(None),
                ReminderSchedule.next_trigger_at >= window_start,
                ReminderSchedule.next_trigger_at <= now,
            )
            .first()
        )
        return recent_trigger is not None

    def can_send_proactive(self, user_id: UUID) -> bool:
        """
        Check if a proactive message can be sent to user (no active cooldown).

        Args:
            user_id: The user ID to check.

        Returns:
            True if a proactive message can be sent, False if in cooldown.
        """
        return not self.is_cooldown_active(user_id)

    def schedule_trigger(
        self,
        user_id: UUID,
        trigger_type: str,
        delay_hours: int,
        message: str,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Schedule a one-time proactive trigger.

        Args:
            user_id: The user ID to schedule the trigger for.
            trigger_type: Type of trigger (health_followup, checkin, break_reminder, silent_user).
            delay_hours: Hours to wait before triggering.
            message: The message to send.
            title: Optional title for the reminder. Defaults to trigger_type.

        Returns:
            Dictionary with:
                - scheduled: bool indicating success
                - trigger_id: UUID of the created reminder schedule
        """
        if trigger_type not in VALID_TRIGGER_TYPES:
            raise ValueError(f"Invalid trigger_type: {trigger_type}. Must be one of {VALID_TRIGGER_TYPES}")

        # Check cooldown first
        if not self.can_send_proactive(user_id):
            return {
                "scheduled": False,
                "trigger_id": None,
                "reason": "cooldown_active",
            }

        now = utcnow_naive()
        run_at = now + timedelta(hours=delay_hours)

        schedule = ReminderSchedule(
            user_id=user_id,
            reminder_type=trigger_type,
            title=title or trigger_type.replace("_", " ").title(),
            message=message,
            schedule_kind="one_time",
            run_at=run_at,
            timezone="UTC",
            status="active",
            next_trigger_at=run_at,
            payload={"trigger_type": trigger_type, "source": "proactive_trigger"},
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)

        return {
            "scheduled": True,
            "trigger_id": schedule.id,
        }

    def schedule_health_followup(
        self,
        user_id: UUID,
        message: str = "Just checking in – how are you feeling now?",
        delay_hours: int = 3,
    ) -> Dict[str, Any]:
        """
        Schedule a health follow-up trigger.

        Convenience method that schedules a health_followup trigger
        after a delay (default 3 hours).

        Args:
            user_id: The user ID.
            message: Follow-up message.
            delay_hours: Hours to wait (default 3).

        Returns:
            Dictionary with scheduled status and trigger_id.
        """
        return self.schedule_trigger(
            user_id=user_id,
            trigger_type="health_followup",
            delay_hours=delay_hours,
            message=message,
        )

    def schedule_break_reminder(
        self,
        user_id: UUID,
        message: str = "Hey, you've been active for a while. Take a quick break?",
        delay_hours: int = 0,
    ) -> Dict[str, Any]:
        """
        Schedule a break reminder trigger.

        Convenience method for break_reminder triggers.
        Usually with short or zero delay.

        Args:
            user_id: The user ID.
            message: Break reminder message.
            delay_hours: Hours to wait (default 0 for immediate).

        Returns:
            Dictionary with scheduled status and trigger_id.
        """
        return self.schedule_trigger(
            user_id=user_id,
            trigger_type="break_reminder",
            delay_hours=delay_hours,
            message=message,
        )

    def schedule_checkin(
        self,
        user_id: UUID,
        message: str = "Hey! Just checking in – how are things going?",
        delay_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Schedule a check-in trigger.

        Convenience method for regular check-ins.
        Default delay of 24 hours.

        Args:
            user_id: The user ID.
            message: Check-in message.
            delay_hours: Hours to wait (default 24).

        Returns:
            Dictionary with scheduled status and trigger_id.
        """
        return self.schedule_trigger(
            user_id=user_id,
            trigger_type="checkin",
            delay_hours=delay_hours,
            message=message,
        )

    def schedule_silent_user_followup(
        self,
        user_id: UUID,
        message: str = "Haven't heard from you in a while – everything okay?",
        delay_hours: int = 48,
    ) -> Dict[str, Any]:
        """
        Schedule a silent user follow-up trigger.

        Convenience method for following up with quiet users.
        Default delay of 48 hours.

        Args:
            user_id: The user ID.
            message: Follow-up message.
            delay_hours: Hours to wait (default 48).

        Returns:
            Dictionary with scheduled status and trigger_id.
        """
        return self.schedule_trigger(
            user_id=user_id,
            trigger_type="silent_user",
            delay_hours=delay_hours,
            message=message,
        )


def on_health_detected(
    db: Session,
    user_id: UUID,
    health_result: dict,
) -> Dict[str, Any]:
    """
    Schedule follow-up when health concerns detected.

    Call this after detect_health_keywords() returns has_health_concern=True.
    Schedules a 3-hour follow-up if severity is medium or high.

    Args:
        db: Database session.
        user_id: User ID.
        health_result: Result from detect_health_keywords().

    Returns:
        Dictionary with scheduled status and trigger_id.
    """
    if not health_result.get("has_health_concern"):
        return {"scheduled": False, "trigger_id": None, "reason": "no_health_concern"}

    severity = health_result.get("severity", "none")
    if severity in ("medium", "high"):
        service = ProactiveTriggerService(db)
        return service.schedule_health_followup(user_id=user_id, delay_hours=3)

    return {"scheduled": False, "trigger_id": None, "reason": "low_severity"}


def schedule_trigger(
    db: Session,
    user_id: UUID,
    trigger_type: str,
    delay_hours: int,
    message: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    service = ProactiveTriggerService(db)
    return service.schedule_trigger(user_id, trigger_type, delay_hours, message, title)


def can_send_proactive(db: Session, user_id: UUID) -> bool:
    """Standalone function wrapper for ProactiveTriggerService.can_send_proactive."""
    service = ProactiveTriggerService(db)
    return service.can_send_proactive(user_id)


def is_cooldown_active(db: Session, user_id: UUID) -> bool:
    """Standalone function wrapper for ProactiveTriggerService.is_cooldown_active."""
    service = ProactiveTriggerService(db)
    return service.is_cooldown_active(user_id)


def get_proactive_trigger_service(db: Session) -> ProactiveTriggerService:
    return ProactiveTriggerService(db)