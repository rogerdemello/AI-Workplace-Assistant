"""Proactive check-ins must actually reach the employee.

The scheduler jobs that spot a quiet or overloaded employee write a
ReminderSchedule row; MarkProactiveService.process_due_reminders only picks up
rows with status "active". These jobs previously wrote them as "cancelled", so
the nudge was recorded and never delivered — exactly the silent-employee case
the product exists to catch. These tests pin the delivery contract.
"""

from datetime import timedelta

import pytest

from app.core.time import utcnow_naive
from app.models.activity_event import ActivityEvent
from app.models.reminder_schedule import ReminderSchedule


@pytest.fixture
def quiet_employee(db, test_user):
    """An employee who is online now but hasn't sent a message in days.

    The jobs skip users who aren't currently active, so seed a recent activity
    event — that's what ``is_user_active`` looks at.
    """
    db.add(
        ActivityEvent(
            user_id=test_user.id,
            event_type="page_view",
            event_source="web",
            event_at=utcnow_naive(),
        )
    )
    db.commit()
    return test_user


def test_silent_user_job_schedules_a_deliverable_reminder(db, quiet_employee):
    from app.services.scheduler import check_silent_users

    result = check_silent_users()
    assert result.get("error") is None, result
    assert result["silent_users"] >= 1

    reminder = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == quiet_employee.id,
            ReminderSchedule.reminder_type == "silent_user",
        )
        .first()
    )
    assert reminder is not None, "silent-user job did not schedule a check-in"
    assert reminder.status == "active", (
        "check-in was scheduled as non-active, so process_due_reminders will "
        "never deliver it"
    )
    assert reminder.next_trigger_at is not None


def test_scheduled_check_in_is_picked_up_for_delivery(db, quiet_employee):
    from app.services.mark_proactive import MarkProactiveService
    from app.services.scheduler import check_silent_users

    check_silent_users()

    # Make sure the row is unambiguously due.
    reminder = (
        db.query(ReminderSchedule)
        .filter(ReminderSchedule.user_id == quiet_employee.id)
        .first()
    )
    assert reminder is not None
    reminder.next_trigger_at = utcnow_naive() - timedelta(minutes=1)
    db.commit()

    result = MarkProactiveService(db).process_due_reminders()
    assert result["sent"] >= 1, "due check-in was not delivered"


def test_pto_nudge_is_deliverable(db, test_user):
    """An employee with no leave on record is overdue a break."""
    from app.services.scheduler import check_pto_nudges

    result = check_pto_nudges()
    assert result.get("error") is None, result

    reminder = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == test_user.id,
            ReminderSchedule.reminder_type == "pto_reminder",
        )
        .first()
    )
    assert reminder is not None, "PTO nudge was never scheduled"
    assert reminder.status == "active", "PTO nudge would never be delivered"


def test_meeting_fatigue_nudge_is_deliverable(db, quiet_employee):
    from app.models.meeting_event import MeetingEvent
    from app.services.scheduler import check_meeting_fatigue

    now = utcnow_naive()
    for index in range(6):  # threshold is 5
        db.add(
            MeetingEvent(
                user_id=quiet_employee.id,
                meeting_title=f"Sync {index}",
                duration_minutes=60,
                meeting_at=now,
            )
        )
    db.commit()

    result = check_meeting_fatigue()
    assert result.get("error") is None, result

    reminder = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == quiet_employee.id,
            ReminderSchedule.reminder_type == "meeting_fatigue",
        )
        .first()
    )
    assert reminder is not None, "meeting-fatigue nudge was never scheduled"
    assert reminder.status == "active", "meeting-fatigue nudge would never be delivered"


def test_wellness_nudge_is_deliverable(db, quiet_employee, monkeypatch):
    """The job is time-gated to 10:00-10:30 and 14:00-14:30, so pin the clock."""
    from app.models.wellness_tip import WellnessTip, WellnessTipType
    from app.services import scheduler as scheduler_module

    db.add(
        WellnessTip(
            tip_type=WellnessTipType.hydration,
            title="Water break",
            content="Keep a bottle nearby.",
            emoji="💧",
            is_active=True,
        )
    )
    db.commit()

    pinned = utcnow_naive().replace(hour=10, minute=5, second=0, microsecond=0)
    # is_user_active reads the same pinned clock, so the activity has to sit
    # inside its 30-minute window rather than at real "now".
    db.add(
        ActivityEvent(
            user_id=quiet_employee.id,
            event_type="page_view",
            event_source="web",
            event_at=pinned - timedelta(minutes=5),
        )
    )
    db.commit()
    monkeypatch.setattr(scheduler_module, "utcnow_naive", lambda: pinned)

    result = scheduler_module.check_wellness_nudges()
    assert result.get("error") is None, result
    assert not result.get("skipped"), result

    reminder = (
        db.query(ReminderSchedule)
        .filter(
            ReminderSchedule.user_id == quiet_employee.id,
            ReminderSchedule.reminder_type == "wellness_nudge",
        )
        .first()
    )
    assert reminder is not None, "wellness nudge was never scheduled"
    assert reminder.status == "active", "wellness nudge would never be delivered"


def test_returning_employee_can_pull_the_check_in_they_missed(
    client, auth_headers, db, quiet_employee
):
    """The chat UI restores from local storage, so persistence alone isn't delivery.

    A returning employee must be able to pull nudges sent while they were away.
    """
    from app.services.mark_proactive import MarkProactiveService
    from app.services.scheduler import check_silent_users

    check_silent_users()
    reminder = (
        db.query(ReminderSchedule)
        .filter(ReminderSchedule.user_id == quiet_employee.id)
        .first()
    )
    reminder.next_trigger_at = utcnow_naive() - timedelta(minutes=1)
    db.commit()
    MarkProactiveService(db).process_due_reminders()

    response = client.get("/api/v1/chat/nudges/pending", headers=auth_headers)
    assert response.status_code == 200, response.text
    nudges = response.json()
    assert nudges, "employee could not retrieve the check-in they missed"
    assert "everything okay" in nudges[0]["text"].lower()
    assert nudges[0]["nudge_type"] == "silent_user"


def test_watermark_stops_the_same_nudge_arriving_twice(
    client, auth_headers, db, quiet_employee
):
    from app.services.mark_proactive import MarkProactiveService
    from app.services.scheduler import check_silent_users

    check_silent_users()
    reminder = (
        db.query(ReminderSchedule)
        .filter(ReminderSchedule.user_id == quiet_employee.id)
        .first()
    )
    reminder.next_trigger_at = utcnow_naive() - timedelta(minutes=1)
    db.commit()
    MarkProactiveService(db).process_due_reminders()

    first = client.get("/api/v1/chat/nudges/pending", headers=auth_headers).json()
    assert first

    # Client stores the newest timestamp and passes it back on the next open.
    watermark = first[-1]["created_at"]
    second = client.get(
        f"/api/v1/chat/nudges/pending?since={watermark}", headers=auth_headers
    ).json()
    assert second == [], "already-seen nudge was served again"


def test_ordinary_bot_replies_are_not_served_as_nudges(client, auth_headers, test_user):
    """Only proactively-sent messages qualify — not normal conversation."""
    client.post(
        "/api/v1/chat/message", headers=auth_headers, json={"message": "hello there"}
    )
    response = client.get("/api/v1/chat/nudges/pending", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_check_in_waits_in_chat_history_when_employee_is_offline(db, quiet_employee):
    """A quiet employee has no open chat, so SSE alone would drop the nudge."""
    from app.models.conversation import Conversation, Message, MessageSender
    from app.services.mark_proactive import MarkProactiveService
    from app.services.scheduler import check_silent_users

    check_silent_users()
    reminder = (
        db.query(ReminderSchedule)
        .filter(ReminderSchedule.user_id == quiet_employee.id)
        .first()
    )
    reminder.next_trigger_at = utcnow_naive() - timedelta(minutes=1)
    db.commit()

    MarkProactiveService(db).process_due_reminders()

    persisted = (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Conversation.user_id == quiet_employee.id,
            Message.sender == MessageSender.bot,
        )
        .all()
    )
    assert persisted, "check-in vanished — nothing waiting when the employee returns"
    assert any("everything okay" in (m.message_text or "").lower() for m in persisted)
