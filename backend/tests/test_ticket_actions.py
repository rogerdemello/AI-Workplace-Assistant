from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import status

from app.models.ticket import Ticket
from app.models.action import HRAction
from app.models.hr_notification import HrNotification


def test_hr_can_assign_ticket(client, auth_headers, hr_auth_headers, hr_user, db):
    create_resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={"query": "Need payroll help", "category": "payroll", "priority": "medium"},
    )
    assert create_resp.status_code == status.HTTP_200_OK
    ticket_id = create_resp.json()["id"]

    assign_resp = client.post(
        f"/api/v1/tickets/{ticket_id}/assign",
        headers=hr_auth_headers,
        json={"assignee_id": str(hr_user.id)},
    )

    assert assign_resp.status_code == status.HTTP_200_OK
    payload = assign_resp.json()
    assert payload["assigned_to"] == str(hr_user.id)
    assert payload["status"] == "in_progress"


def test_hr_can_bulk_update_tickets(client, auth_headers, hr_auth_headers, hr_user):
    ticket_ids = []
    for idx in range(2):
        create_resp = client.post(
            "/api/v1/tickets",
            headers=auth_headers,
            json={
                "query": f"Ticket {idx}",
                "category": "general",
                "priority": "low",
            },
        )
        assert create_resp.status_code == status.HTTP_200_OK
        ticket_ids.append(create_resp.json()["id"])

    bulk_resp = client.post(
        "/api/v1/tickets/bulk-action",
        headers=hr_auth_headers,
        json={
            "ticket_ids": ticket_ids,
            "status": "resolved",
            "priority": "high",
            "assigned_to": str(hr_user.id),
        },
    )

    assert bulk_resp.status_code == status.HTTP_200_OK
    payload = bulk_resp.json()
    assert len(payload) == 2
    for item in payload:
        assert item["status"] == "resolved"
        assert item["priority"] == "high"
        assert item["assigned_to"] == str(hr_user.id)


def test_hr_can_enforce_sla_on_overdue_ticket(client, auth_headers, hr_auth_headers, db):
    create_resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={"query": "Slow response issue", "category": "general", "priority": "medium"},
    )
    assert create_resp.status_code == status.HTTP_200_OK
    ticket_id = create_resp.json()["id"]

    ticket = db.query(Ticket).filter(Ticket.id == UUID(ticket_id)).first()
    ticket.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3)
    db.commit()

    enforce_resp = client.post(
        f"/api/v1/tickets/{ticket_id}/enforce-sla",
        headers=hr_auth_headers,
    )

    assert enforce_resp.status_code == status.HTTP_200_OK
    payload = enforce_resp.json()
    assert payload["status"] == "escalated"


def test_hr_can_manually_escalate_ticket(client, auth_headers, hr_auth_headers):
    create_resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={"query": "Manager conflict is escalating", "category": "complaint", "priority": "high"},
    )
    assert create_resp.status_code == status.HTTP_200_OK
    ticket_id = create_resp.json()["id"]

    escalate_resp = client.post(
        f"/api/v1/tickets/{ticket_id}/escalate",
        headers=hr_auth_headers,
        json={"reason": "Escalated by HR panel"},
    )
    assert escalate_resp.status_code == status.HTTP_200_OK
    payload = escalate_resp.json()
    assert payload["status"] == "escalated"
    assert payload["priority"] == "critical"


def test_ticket_action_creates_hr_notification(client, auth_headers, hr_auth_headers, db):
    create_resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={"query": "Need urgent help", "category": "general", "priority": "medium"},
    )
    assert create_resp.status_code == status.HTTP_200_OK
    ticket_id = create_resp.json()["id"]

    escalate_resp = client.post(
        f"/api/v1/tickets/{ticket_id}/escalate",
        headers=hr_auth_headers,
        json={"reason": "Escalated after SLA breach"},
    )
    assert escalate_resp.status_code == status.HTTP_200_OK

    notif = (
        db.query(HrNotification)
        .filter(HrNotification.ticket_id == UUID(ticket_id), HrNotification.notification_type == "ticket_escalated")
        .order_by(HrNotification.created_at.desc())
        .first()
    )
    assert notif is not None
    assert notif.severity == "high"


def test_hr_can_schedule_checkin_from_ticket(client, auth_headers, hr_auth_headers, db):
    create_resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={"query": "Need manager support", "category": "complaint", "priority": "high"},
    )
    assert create_resp.status_code == status.HTTP_200_OK
    ticket_id = create_resp.json()["id"]

    schedule_resp = client.post(
        f"/api/v1/tickets/{ticket_id}/schedule-checkin",
        headers=hr_auth_headers,
        json={"notes": "Set up check-in by Friday"},
    )
    assert schedule_resp.status_code == status.HTTP_200_OK
    assert "Check-in scheduled" in schedule_resp.json()["detail"]

    actions = db.query(HRAction).all()
    assert len(actions) >= 1
    assert actions[0].action_type == "schedule_checkin"


def test_hr_can_close_ticket(client, auth_headers, hr_auth_headers):
    create_resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={"query": "Please resolve this issue", "category": "general", "priority": "medium"},
    )
    assert create_resp.status_code == status.HTTP_200_OK
    ticket_id = create_resp.json()["id"]

    close_resp = client.post(
        f"/api/v1/tickets/{ticket_id}/close",
        headers=hr_auth_headers,
        json={"resolution_note": "Resolved by HR"},
    )
    assert close_resp.status_code == status.HTTP_200_OK
    payload = close_resp.json()
    assert payload["status"] == "resolved"
    assert payload["resolved_at"] is not None
