"""Canonical lifecycle surveys (onboarding, exit, manager/role change) and helpers.

These let proactive lifecycle nudges point at a real, fillable survey instead
of a plain message. ``ensure_lifecycle_surveys`` is idempotent and safe to call
from seed scripts or lazily from the scheduler. ``enqueue_lifecycle_check_in``
schedules a one-time deduped reminder pointing at the survey, used by event-time
triggers (e.g. PATCH user changing manager_id or designation).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..core.time import utcnow_naive
from ..models.automation_action import AutomationAction
from ..models.reminder_schedule import ReminderSchedule
from ..models.survey import Survey

logger = logging.getLogger(__name__)


ONBOARDING_SURVEY = {
    "survey_type": "onboarding",
    "title": "Settling in — your early experience",
    "description": "A quick check-in on how your start has been. Honest answers help us do better.",
    "questions": [
        {"id": "welcome", "type": "rating", "question": "How welcomed have you felt so far? (0–10)", "required": True},
        {"id": "clarity", "type": "rating", "question": "How clear are your role and expectations? (0–10)", "required": True},
        {"id": "support", "type": "choice", "question": "Do you have what you need to do your job?",
         "options": ["Yes, all set", "Mostly", "Missing a few things", "Not really"], "required": True},
        {"id": "open", "type": "longtext", "question": "Anything you wish was different about your start?", "required": False},
    ],
}

EXIT_SURVEY = {
    "survey_type": "exit",
    "title": "Before you go — exit reflections",
    "description": "As you wrap up, your candid feedback genuinely shapes things for the people who follow.",
    "questions": [
        {"id": "reason", "type": "choice", "question": "What's the main reason you're moving on?",
         "options": ["Career growth", "Compensation", "Management", "Work-life balance", "Relocation", "Other"], "required": True},
        {"id": "recommend", "type": "rating", "question": "How likely are you to recommend us as a place to work? (0–10)", "required": True},
        {"id": "best", "type": "longtext", "question": "What worked well during your time here?", "required": False},
        {"id": "improve", "type": "longtext", "question": "What should we improve?", "required": False},
    ],
}

MANAGER_CHANGE_SURVEY = {
    "survey_type": "manager_change",
    "title": "Working with your new manager",
    "description": "A quick check-in now that your reporting line has changed.",
    "questions": [
        {"id": "rapport", "type": "rating", "question": "How comfortable do you feel with your new manager so far? (0–10)", "required": True},
        {"id": "clarity", "type": "rating", "question": "How clear are expectations with the new manager? (0–10)", "required": True},
        {"id": "support", "type": "choice", "question": "Anything that would smooth the transition?",
         "options": ["No, all good", "More 1:1 time", "Clearer expectations", "Working-style help", "Other"], "required": True},
        {"id": "open", "type": "longtext", "question": "Anything else you'd like to share about the change?", "required": False},
    ],
}

ROLE_CHANGE_SURVEY = {
    "survey_type": "role_change",
    "title": "How's the new role?",
    "description": "A short reflection on your role / title change.",
    "questions": [
        {"id": "fit", "type": "rating", "question": "How well does the new role fit you so far? (0–10)", "required": True},
        {"id": "energy", "type": "rating", "question": "How energized do you feel about it? (0–10)", "required": True},
        {"id": "blockers", "type": "choice", "question": "Anything getting in the way of doing this well?",
         "options": ["Nothing", "Skills gap", "Tools / access", "Stakeholder clarity", "Other"], "required": True},
        {"id": "open", "type": "longtext", "question": "What would help you succeed in this role?", "required": False},
    ],
}

_DEFAULT_SURVEYS = [ONBOARDING_SURVEY, EXIT_SURVEY, MANAGER_CHANGE_SURVEY, ROLE_CHANGE_SURVEY]


def get_lifecycle_survey(db: Session, survey_type: str) -> Optional[Survey]:
    """Return the active survey for a lifecycle type, if one exists."""
    return (
        db.query(Survey)
        .filter(Survey.survey_type == survey_type, Survey.is_active.is_(True))
        .order_by(Survey.created_at.desc())
        .first()
    )


def enqueue_lifecycle_check_in(
    db: Session,
    *,
    user_id: UUID,
    kind: str,
    message_text: str,
    dedup_window_days: int = 14,
) -> bool:
    """Schedule a one-time lifecycle check-in nudge with a survey link.

    Dedup per (user, kind) within ``dedup_window_days`` using ``AutomationAction``
    — the same dedup channel onboarding/exit nudges use. Returns True if a new
    nudge was scheduled, False if one was already in flight.
    """
    now = utcnow_naive()
    rule_name = f"lifecycle_{kind}_checkin"
    cutoff = now - timedelta(days=dedup_window_days)

    recent = (
        db.query(AutomationAction.id)
        .filter(AutomationAction.rule_name == rule_name)
        .filter(AutomationAction.user_id == user_id)
        .filter(AutomationAction.executed_at >= cutoff)
        .first()
    )
    if recent:
        return False

    # Make sure the survey exists, then pull its id for the deep link.
    ensure_lifecycle_surveys(db)
    survey = get_lifecycle_survey(db, kind)
    survey_id = str(survey.id) if survey else None

    message = message_text
    payload: dict = {}
    if survey_id:
        link = f"/surveys?survey={survey_id}"
        message = f"{message_text}\n\nShare your feedback here: {link}"
        payload = {"survey_id": survey_id, "action_url": link}

    db.add(
        AutomationAction(
            rule_name=rule_name,
            user_id=user_id,
            target_type="user",
            action_type="nudge",
            status="sent",
            executed_at=now,
            trigger_context={"kind": kind, "survey_id": survey_id},
        )
    )
    db.add(
        ReminderSchedule(
            user_id=user_id,
            reminder_type=f"lifecycle_{kind}",
            title=f"Lifecycle check-in ({kind.replace('_', ' ')})",
            message=message,
            schedule_kind="one_time",
            run_at=now,
            timezone="UTC",
            status="active",
            next_trigger_at=now,
            payload=payload,
        )
    )
    db.commit()
    logger.info("Lifecycle check-in scheduled: user=%s kind=%s", user_id, kind)
    return True


def ensure_lifecycle_surveys(db: Session, created_by: Optional[UUID] = None) -> dict:
    """Create the canonical onboarding + exit surveys if absent. Idempotent.

    Returns a map of survey_type -> survey id (str) for whatever now exists.
    """
    result: dict[str, str] = {}
    for spec in _DEFAULT_SURVEYS:
        existing = get_lifecycle_survey(db, spec["survey_type"])
        if existing is not None:
            result[spec["survey_type"]] = str(existing.id)
            continue
        survey = Survey(
            title=spec["title"],
            description=spec["description"],
            questions=spec["questions"],
            survey_type=spec["survey_type"],
            is_active=True,
            allow_anonymous=spec["survey_type"] == "exit",  # exit feedback is anonymous-friendly
            created_by=created_by,
        )
        db.add(survey)
        db.flush()  # assign id without ending the caller's transaction
        result[spec["survey_type"]] = str(survey.id)
    db.commit()
    return result
