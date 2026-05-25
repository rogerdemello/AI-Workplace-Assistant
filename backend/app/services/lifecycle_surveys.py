"""Canonical lifecycle surveys (onboarding, exit) and lookup helpers.

These let proactive lifecycle nudges point at a real, fillable survey instead
of a plain message. ``ensure_lifecycle_surveys`` is idempotent and safe to call
from seed scripts or lazily from the scheduler.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.survey import Survey


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

_DEFAULT_SURVEYS = [ONBOARDING_SURVEY, EXIT_SURVEY]


def get_lifecycle_survey(db: Session, survey_type: str) -> Optional[Survey]:
    """Return the active survey for a lifecycle type, if one exists."""
    return (
        db.query(Survey)
        .filter(Survey.survey_type == survey_type, Survey.is_active.is_(True))
        .order_by(Survey.created_at.desc())
        .first()
    )


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
