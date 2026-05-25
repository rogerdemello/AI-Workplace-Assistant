"""Phase 3 — medication reminders, anonymous feedback, onboarding nudges."""

from datetime import timedelta

from fastapi import status

from app.core.time import utcnow_naive
from app.models.anonymous_feedback import AnonymousFeedback
from app.models.reminder_schedule import ReminderSchedule
from app.services.health_detector import detect_medication_intent
from app.services.mark_proactive import MarkProactiveService


# ── Medication reminders ────────────────────────────────────────────────────

def test_detect_medication_intent():
    hit = detect_medication_intent("can you remind me to take my insulin every morning")
    assert hit["has_medication_intent"] is True
    assert "insulin" in hit["keywords"]
    miss = detect_medication_intent("I feel great today")
    assert miss["has_medication_intent"] is False


def test_schedule_medication_reminder_creates_active_daily(db, test_user):
    svc = MarkProactiveService(db)
    run_at = utcnow_naive() + timedelta(hours=1)
    row = svc.schedule_medication_reminder(
        user_id=test_user.id, medication="Vitamin D", run_at=run_at, daily=True
    )
    assert row.reminder_type == "medication"
    assert row.schedule_kind == "daily"
    assert row.status == "active"
    assert "Vitamin D" in row.message
    assert row.payload.get("medication") == "Vitamin D"


# ── Anonymous feedback persistence ──────────────────────────────────────────

def test_anonymous_feedback_persists_without_identity(client, db, mock_redis):
    res = client.post(
        "/api/v1/feedback/anonymous",
        json={"category": "workload", "message": "Sprint scope keeps ballooning."},
    )
    assert res.status_code == 200
    token = res.json()["token"]
    assert token

    # Persisted, with no user linkage and only a hashed token.
    rows = db.query(AnonymousFeedback).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.category == "workload"
    assert row.message == "Sprint scope keeps ballooning."
    assert row.token_hash and row.token_hash != token  # stored hash, not raw token
    assert not hasattr(row, "user_id")  # anonymity is structural

    # Status is checkable via the one-time token.
    status_res = client.get("/api/v1/feedback/anonymous/status", params={"token": token})
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "submitted"
    assert status_res.json()["category"] == "workload"


def test_anonymous_feedback_status_unknown_token_404(client, mock_redis):
    res = client.get("/api/v1/feedback/anonymous/status", params={"token": "not-a-real-token"})
    assert res.status_code == 404


# ── Onboarding survey nudges ────────────────────────────────────────────────

def test_onboarding_nudge_fires_on_day_7(db, test_user):
    from app.services import scheduler

    # Backdate the user's creation to exactly 7 days ago.
    test_user.created_at = utcnow_naive() - timedelta(days=7)
    db.commit()

    result = scheduler.check_onboarding_surveys()
    assert result.get("sent", 0) >= 1

    reminders = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == test_user.id,
            ReminderSchedule.reminder_type == "onboarding_survey",
        )
        .all()
    )
    assert len(reminders) == 1
    assert reminders[0].status == "active"

    # Idempotent — running again creates no duplicate.
    scheduler.check_onboarding_surveys()
    reminders_again = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == test_user.id,
            ReminderSchedule.reminder_type == "onboarding_survey",
        )
        .all()
    )
    assert len(reminders_again) == 1


def test_onboarding_nudge_skips_non_milestone_day(db, test_user):
    from app.services import scheduler

    test_user.created_at = utcnow_naive() - timedelta(days=4)  # not a milestone
    db.commit()

    scheduler.check_onboarding_surveys()
    reminders = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == test_user.id,
            ReminderSchedule.reminder_type == "onboarding_survey",
        )
        .all()
    )
    assert len(reminders) == 0


def test_exit_survey_fires_near_departure(db, test_user):
    from app.services import scheduler

    test_user.departure_at = utcnow_naive() + timedelta(days=1)
    db.commit()

    result = scheduler.check_exit_surveys()
    assert result.get("sent", 0) >= 1

    reminders = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == test_user.id,
            ReminderSchedule.reminder_type == "exit_survey",
        )
        .all()
    )
    assert len(reminders) == 1

    # Idempotent on re-run.
    scheduler.check_exit_surveys()
    again = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == test_user.id,
            ReminderSchedule.reminder_type == "exit_survey",
        )
        .all()
    )
    assert len(again) == 1


def test_exit_survey_skips_when_no_departure(db, test_user):
    from app.services import scheduler

    test_user.departure_at = None
    db.commit()
    scheduler.check_exit_surveys()
    reminders = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == test_user.id,
            ReminderSchedule.reminder_type == "exit_survey",
        )
        .all()
    )
    assert len(reminders) == 0
