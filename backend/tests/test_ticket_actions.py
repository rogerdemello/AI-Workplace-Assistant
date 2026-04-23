from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import status

from app.models.ticket import Ticket


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
