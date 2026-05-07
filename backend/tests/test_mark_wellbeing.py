from datetime import timedelta

from fastapi import status
from app.core.time import utcnow_naive


def test_reminder_lifecycle(client, auth_headers, mock_redis):
    run_at = (utcnow_naive() + timedelta(hours=1)).isoformat()
    create_response = client.post(
        "/api/v1/wellbeing/reminders",
        headers=auth_headers,
        json={
            "reminder_type": "medicine",
            "title": "Medicine reminder",
            "message": "Take your medicine",
            "schedule_kind": "one_time",
            "run_at": run_at,
        },
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    created = create_response.json()
    reminder_id = created["id"]
    assert created["status"] == "active"
    assert created["reminder_type"] == "medicine"

    list_response = client.get("/api/v1/wellbeing/reminders", headers=auth_headers)
    assert list_response.status_code == status.HTTP_200_OK
    reminders = list_response.json()
    assert any(r["id"] == reminder_id for r in reminders)

    patch_response = client.patch(
        f"/api/v1/wellbeing/reminders/{reminder_id}",
        headers=auth_headers,
        json={"status": "paused"},
    )
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.json()["status"] == "paused"

    delete_response = client.delete(
        f"/api/v1/wellbeing/reminders/{reminder_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    list_cancelled = client.get(
        "/api/v1/wellbeing/reminders?include_cancelled=true",
        headers=auth_headers,
    )
    assert list_cancelled.status_code == status.HTTP_200_OK
    reminders_with_cancelled = list_cancelled.json()
    reminder_row = next((r for r in reminders_with_cancelled if r["id"] == reminder_id), None)
    assert reminder_row is not None
    assert reminder_row["status"] == "cancelled"


def test_daily_checkin_updates_risk_and_hr_views(client, auth_headers, hr_auth_headers, mock_redis):
    checkin = client.post(
        "/api/v1/wellbeing/check-ins/daily",
        headers=auth_headers,
        json={
            "mood": "stressed",
            "message": "I am overwhelmed and stressed with deadlines",
            "wants_followup": True,
        },
    )
    assert checkin.status_code == status.HTTP_201_CREATED
    data = checkin.json()
    assert data["signal"]["triage_level"] in ["watch", "high"]
    assert "suggested_next_step" in data

    forbidden = client.get("/api/v1/wellbeing/high-risk", headers=auth_headers)
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN

    high_risk = client.get("/api/v1/wellbeing/high-risk", headers=hr_auth_headers)
    assert high_risk.status_code == status.HTTP_200_OK
    rows = high_risk.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert "risk_level" in rows[0]

    summary = client.get("/api/v1/wellbeing/weekly-summary", headers=hr_auth_headers)
    assert summary.status_code == status.HTTP_200_OK
    weekly = summary.json()
    assert weekly["window_days"] == 7
    assert "high_risk_employees" in weekly
    assert "top_issues" in weekly


def test_activity_events_can_trigger_break_nudge(client, auth_headers, mock_redis):
    last = None
    for _ in range(6):
        resp = client.post(
            "/api/v1/wellbeing/activity",
            headers=auth_headers,
            json={"event_type": "chat_message", "event_source": "web"},
        )
        assert resp.status_code == status.HTTP_200_OK
        last = resp.json()

    assert last is not None
    assert "nudge" in last


def test_hr_can_update_proactive_suppression_policy(client, hr_auth_headers, auth_headers):
    denied = client.get("/api/v1/wellbeing/policy-suppression", headers=auth_headers)
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    current = client.get("/api/v1/wellbeing/policy-suppression", headers=hr_auth_headers)
    assert current.status_code == status.HTTP_200_OK
    assert "global_daily_max" in current.json()

    updated = client.patch(
        "/api/v1/wellbeing/policy-suppression",
        headers=hr_auth_headers,
        json={
            "enabled": True,
            "global_daily_max": 1,
            "break_nudge_cooldown_minutes": 999,
            "break_nudge_daily_max": 1,
        },
    )
    assert updated.status_code == status.HTTP_200_OK
    payload = updated.json()
    assert payload["global_daily_max"] == 1
    assert payload["break_nudge_daily_max"] == 1


def test_break_nudge_is_suppressed_after_policy_limit(client, auth_headers, hr_auth_headers, mock_redis):
    policy = client.patch(
        "/api/v1/wellbeing/policy-suppression",
        headers=hr_auth_headers,
        json={
            "enabled": True,
            "global_daily_max": 1,
            "break_nudge_cooldown_minutes": 999,
            "break_nudge_daily_max": 1,
        },
    )
    assert policy.status_code == status.HTTP_200_OK

    first = None
    for _ in range(6):
        resp = client.post(
            "/api/v1/wellbeing/activity",
            headers=auth_headers,
            json={"event_type": "chat_message", "event_source": "web"},
        )
        assert resp.status_code == status.HTTP_200_OK
        first = resp.json()
    assert first is not None
    assert first.get("nudge")

    second = None
    for _ in range(6):
        resp = client.post(
            "/api/v1/wellbeing/activity",
            headers=auth_headers,
            json={"event_type": "chat_message", "event_source": "web"},
        )
        assert resp.status_code == status.HTTP_200_OK
        second = resp.json()
    assert second is not None
    assert second.get("nudge") is None


def test_reminder_created_event_rule_creates_hr_notification(client, auth_headers, hr_auth_headers, mock_redis):
    create_rule = client.post(
        "/api/v1/automations/rules",
        headers=hr_auth_headers,
        json={
            "name": "Notify on reminder created",
            "event_type": "reminder_created",
            "conditions": {},
            "actions": {
                "create_hr_notification": True,
                "notification_title": "Reminder created automation",
                "notification_type": "reminder_created_workflow",
            },
        },
    )
    assert create_rule.status_code == status.HTTP_200_OK

    run_at = (utcnow_naive() + timedelta(hours=2)).isoformat()
    response = client.post(
        "/api/v1/wellbeing/reminders",
        headers=auth_headers,
        json={
            "reminder_type": "hydration",
            "title": "Hydration reminder",
            "message": "Drink water",
            "schedule_kind": "one_time",
            "run_at": run_at,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    notifications = client.get("/api/v1/portal/hr/notifications", headers=hr_auth_headers)
    assert notifications.status_code == status.HTTP_200_OK
    rows = notifications.json()
    assert any(row.get("notification_type") == "reminder_created_workflow" for row in rows)
