"""Phase 4 — lifecycle surveys: targeting, seeding, and nudge linkage."""

from datetime import timedelta

from fastapi import status

from app.core.time import utcnow_naive
from app.models.reminder_schedule import ReminderSchedule
from app.models.survey import Survey
from app.services.lifecycle_surveys import ensure_lifecycle_surveys, get_lifecycle_survey


# ── Targeting + seeding ─────────────────────────────────────────────────────

def test_ensure_lifecycle_surveys_idempotent(db):
    first = ensure_lifecycle_surveys(db)
    assert set(first.keys()) == {"onboarding", "exit", "manager_change", "role_change"}

    second = ensure_lifecycle_surveys(db)
    assert second == first  # same ids, no duplicates

    # Exactly one of each type exists.
    for stype in ("onboarding", "exit", "manager_change", "role_change"):
        rows = db.query(Survey).filter(Survey.survey_type == stype).all()
        assert len(rows) == 1


def test_get_lifecycle_survey_returns_active(db):
    ensure_lifecycle_surveys(db)
    onboarding = get_lifecycle_survey(db, "onboarding")
    assert onboarding is not None
    assert onboarding.survey_type == "onboarding"
    assert onboarding.is_active is True
    assert len(onboarding.questions) > 0


def test_survey_type_surfaces_in_api(client, hr_auth_headers, mock_redis):
    res = client.post(
        "/api/v1/surveys",
        headers=hr_auth_headers,
        json={
            "title": "Pulse check",
            "description": "weekly",
            "questions": [{"id": "q1", "type": "rating", "question": "How's the week?"}],
            "survey_type": "pulse",
        },
    )
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["survey_type"] == "pulse"

    listed = client.get("/api/v1/surveys", headers=hr_auth_headers)
    assert listed.status_code == status.HTTP_200_OK
    assert any(s.get("survey_type") == "pulse" for s in listed.json())


# ── Lifecycle nudges link the survey ────────────────────────────────────────

def test_onboarding_nudge_links_survey(db, test_user):
    from app.services import scheduler

    test_user.created_at = utcnow_naive() - timedelta(days=7)
    db.commit()

    scheduler.check_onboarding_surveys()

    reminder = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == test_user.id,
            ReminderSchedule.reminder_type == "onboarding_survey",
        )
        .first()
    )
    assert reminder is not None
    survey = get_lifecycle_survey(db, "onboarding")
    assert survey is not None
    # The nudge carries the survey link in message + payload (for the SSE CTA).
    assert f"/surveys?survey={survey.id}" in reminder.message
    assert reminder.payload.get("survey_id") == str(survey.id)
    assert reminder.payload.get("action_url") == f"/surveys?survey={survey.id}"


def test_exit_nudge_links_survey(db, test_user):
    from app.services import scheduler

    test_user.departure_at = utcnow_naive() + timedelta(days=1)
    db.commit()

    scheduler.check_exit_surveys()

    reminder = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == test_user.id,
            ReminderSchedule.reminder_type == "exit_survey",
        )
        .first()
    )
    assert reminder is not None
    survey = get_lifecycle_survey(db, "exit")
    assert survey is not None
    assert f"/surveys?survey={survey.id}" in reminder.message
    assert reminder.payload.get("survey_id") == str(survey.id)
