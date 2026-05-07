from fastapi import status
from datetime import date, timedelta


def test_hr_can_create_and_list_automation_rules(client, hr_auth_headers):
    create_response = client.post(
        "/api/v1/automations/rules",
        headers=hr_auth_headers,
        json={
            "name": "Auto escalate complaints",
            "event_type": "ticket_created",
            "conditions": {"category_in": ["complaint"]},
            "actions": {"auto_escalate": True, "set_priority": "critical"},
        },
    )
    assert create_response.status_code == status.HTTP_200_OK
    created = create_response.json()
    assert created["name"] == "Auto escalate complaints"

    list_response = client.get("/api/v1/automations/rules", headers=hr_auth_headers)
    assert list_response.status_code == status.HTTP_200_OK
    rows = list_response.json()
    assert any(row["id"] == created["id"] for row in rows)


def test_employee_cannot_create_automation_rules(client, auth_headers):
    response = client.post(
        "/api/v1/automations/rules",
        headers=auth_headers,
        json={
            "name": "Should fail",
            "event_type": "ticket_created",
            "conditions": {},
            "actions": {},
        },
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_ticket_creation_applies_matching_automation_rule(client, auth_headers, hr_auth_headers):
    create_rule = client.post(
        "/api/v1/automations/rules",
        headers=hr_auth_headers,
        json={
            "name": "Escalate complaints",
            "event_type": "ticket_created",
            "conditions": {"category_in": ["complaint"]},
            "actions": {"auto_escalate": True, "set_priority": "critical"},
        },
    )
    assert create_rule.status_code == status.HTTP_200_OK

    ticket_response = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={"query": "Manager harassment incident", "category": "complaint", "priority": "medium"},
    )
    assert ticket_response.status_code == status.HTTP_200_OK
    payload = ticket_response.json()
    assert payload["status"] == "escalated"
    assert payload["priority"] == "critical"


def test_ticket_update_applies_matching_automation_rule(client, auth_headers, hr_auth_headers):
    create_rule = client.post(
        "/api/v1/automations/rules",
        headers=hr_auth_headers,
        json={
            "name": "Raise priority when ticket moves to in progress",
            "event_type": "ticket_updated",
            "conditions": {"to_status_in": ["in_progress"]},
            "actions": {"set_priority": "high"},
        },
    )
    assert create_rule.status_code == status.HTTP_200_OK

    ticket_response = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={"query": "Need help with VPN setup", "category": "it", "priority": "low"},
    )
    assert ticket_response.status_code == status.HTTP_200_OK
    ticket_id = ticket_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers=hr_auth_headers,
        json={"status": "in_progress"},
    )
    assert update_response.status_code == status.HTTP_200_OK
    payload = update_response.json()
    assert payload["status"] == "in_progress"
    assert payload["priority"] == "high"


def test_leave_review_applies_matching_automation_rule(client, auth_headers, hr_auth_headers):
    create_rule = client.post(
        "/api/v1/automations/rules",
        headers=hr_auth_headers,
        json={
            "name": "Add automated leave note",
            "event_type": "leave_reviewed",
            "conditions": {"leave_status_in": ["approved"]},
            "actions": {"set_review_comment_template": "Auto review: leave is {status}."},
        },
    )
    assert create_rule.status_code == status.HTTP_200_OK

    start = date.today() + timedelta(days=2)
    end = start + timedelta(days=1)
    leave_response = client.post(
        "/api/v1/leave",
        headers=auth_headers,
        json={
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "leave_type": "paid",
            "reason": "Family event",
        },
    )
    assert leave_response.status_code == status.HTTP_201_CREATED
    leave_id = leave_response.json()["id"]

    approve_response = client.patch(
        f"/api/v1/leave/{leave_id}/approve",
        headers=hr_auth_headers,
        json={},
    )
    assert approve_response.status_code == status.HTTP_200_OK
    approved = approve_response.json()
    assert approved["status"] == "approved"
    assert approved["review_comment"] == "Auto review: leave is approved."


def test_daily_checkin_automation_can_notify_hr(client, auth_headers, hr_auth_headers):
    create_rule = client.post(
        "/api/v1/automations/rules",
        headers=hr_auth_headers,
        json={
            "name": "Notify HR for stressed checkins",
            "event_type": "daily_checkin_recorded",
            "conditions": {"signal_triage_in": ["high", "watch"], "mood_in": ["stressed", "low"]},
            "actions": {
                "create_hr_notification": True,
                "notification_title": "Wellbeing automation",
                "notification_type": "wellbeing_automation",
            },
        },
    )
    assert create_rule.status_code == status.HTTP_200_OK

    checkin = client.post(
        "/api/v1/wellbeing/check-ins/daily",
        headers=auth_headers,
        json={"mood": "stressed", "message": "I feel overwhelmed", "wants_followup": True},
    )
    assert checkin.status_code == status.HTTP_201_CREATED

    notifications = client.get("/api/v1/portal/hr/notifications", headers=hr_auth_headers)
    assert notifications.status_code == status.HTTP_200_OK
    rows = notifications.json()
    assert any(row.get("notification_type") == "wellbeing_automation" for row in rows)


def test_ticket_close_event_rule_creates_hr_notification(client, auth_headers, hr_auth_headers):
    create_rule = client.post(
        "/api/v1/automations/rules",
        headers=hr_auth_headers,
        json={
            "name": "Notify on ticket close event",
            "event_type": "ticket_closed",
            "conditions": {},
            "actions": {
                "create_hr_notification": True,
                "notification_title": "Closure automation",
                "notification_type": "ticket_closed_workflow",
            },
        },
    )
    assert create_rule.status_code == status.HTTP_200_OK

    ticket_response = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={"query": "Please help with system access", "category": "it", "priority": "medium"},
    )
    assert ticket_response.status_code == status.HTTP_200_OK
    ticket_id = ticket_response.json()["id"]

    close_response = client.post(
        f"/api/v1/tickets/{ticket_id}/close",
        headers=hr_auth_headers,
        json={"resolution_note": "Resolved and confirmed with employee"},
    )
    assert close_response.status_code == status.HTTP_200_OK
    assert close_response.json()["status"] == "resolved"

    notifications = client.get("/api/v1/portal/hr/notifications", headers=hr_auth_headers)
    assert notifications.status_code == status.HTTP_200_OK
    rows = notifications.json()
    assert any(row.get("notification_type") == "ticket_closed_workflow" for row in rows)


def test_leave_requested_event_rule_creates_hr_notification(client, auth_headers, hr_auth_headers):
    create_rule = client.post(
        "/api/v1/automations/rules",
        headers=hr_auth_headers,
        json={
            "name": "Notify on leave requested",
            "event_type": "leave_requested",
            "conditions": {},
            "actions": {
                "create_hr_notification": True,
                "notification_title": "Leave requested automation",
                "notification_type": "leave_requested_workflow",
            },
        },
    )
    assert create_rule.status_code == status.HTTP_200_OK

    from datetime import date, timedelta

    start = date.today() + timedelta(days=4)
    end = start + timedelta(days=1)
    leave_response = client.post(
        "/api/v1/leave",
        headers=auth_headers,
        json={
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "leave_type": "paid",
            "reason": "Family plans",
        },
    )
    assert leave_response.status_code == status.HTTP_201_CREATED

    notifications = client.get("/api/v1/portal/hr/notifications", headers=hr_auth_headers)
    assert notifications.status_code == status.HTTP_200_OK
    rows = notifications.json()
    assert any(row.get("notification_type") == "leave_requested_workflow" for row in rows)
