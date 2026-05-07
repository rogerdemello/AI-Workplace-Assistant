"""HR notifications when repeated negative chat sentiment crosses configurable thresholds."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from ..config import settings
from ..core.time import utcnow_naive
from ..models.hr_notification import HrNotification

SUSTAINED_NOTIFICATION_TYPE = "sustained_sentiment_risk"


def notify_sustained_negative_pattern_if_needed(
    db: Session,
    *,
    employee_id: UUID,
    negative_count_in_window: int,
    window_days: int,
) -> bool:
    """
    Create a single HR inbox notification when negative sentiment logs exceed the minimum
    within the lookback window. Deduped by cooldown so HR is not spammed on every message.
    """
    if not settings.SUSTAINED_RISK_ALERTS_ENABLED:
        return False

    min_msgs = max(1, int(settings.SUSTAINED_NEGATIVE_MIN_MESSAGES))
    if negative_count_in_window < min_msgs:
        return False

    cooldown_hours = max(1, int(settings.SUSTAINED_RISK_ALERT_COOLDOWN_HOURS))
    since = utcnow_naive() - timedelta(hours=cooldown_hours)
    existing = (
        db.query(HrNotification.id)
        .filter(
            HrNotification.actor_id == employee_id,
            HrNotification.notification_type == SUSTAINED_NOTIFICATION_TYPE,
            HrNotification.created_at >= since,
        )
        .first()
    )
    if existing:
        return False

    wd = max(1, int(window_days))
    db.add(
        HrNotification(
            ticket_id=None,
            actor_id=employee_id,
            title="Sustained negative sentiment pattern",
            body=(
                f"Repeated negative chat signals detected ({negative_count_in_window} in the last "
                f"{wd} days). Consider a wellbeing check-in. Message text is not included."
            ),
            notification_type=SUSTAINED_NOTIFICATION_TYPE,
            severity="high",
        )
    )
    db.commit()
    return True


__all__ = ["notify_sustained_negative_pattern_if_needed", "SUSTAINED_NOTIFICATION_TYPE"]
