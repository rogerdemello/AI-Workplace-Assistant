"""Confidentiality boundaries on manager-facing views.

An employee who raises something anonymously, or takes it to HR directly, must
not be surfaced to the manager they may be escaping. These tests pin the
promises the product makes rather than the shape of any one endpoint.
"""

import pytest
from fastapi import status

from app.models.ticket import Ticket, TicketStatus


@pytest.fixture
def report_of_manager(db, test_user, manager_user):
    test_user.manager_id = manager_user.id
    db.commit()
    return test_user


def _add_ticket(db, user_id, *, anonymous: bool):
    ticket = Ticket(
        user_id=user_id,
        query="My manager keeps overriding me in public",
        category="complaint",
        status=TicketStatus.open,
        is_anonymous=anonymous,
    )
    db.add(ticket)
    db.commit()
    return ticket


def test_anonymous_ticket_is_not_counted_against_a_named_report(
    client, manager_auth_headers, db, report_of_manager
):
    """A count of 1 against one person identifies the anonymous author."""
    _add_ticket(db, report_of_manager.id, anonymous=True)

    response = client.get("/api/v1/portal/manager/team", headers=manager_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["open_tickets"] == 0, "anonymous complaint exposed to the manager"
    assert rows[0]["needs_attention"] is not True or rows[0]["sentiment"] in {
        "watch",
        "at_risk",
    }


def test_named_ticket_is_still_counted(client, manager_auth_headers, db, report_of_manager):
    """Non-anonymous tickets are the manager's business — don't over-correct."""
    _add_ticket(db, report_of_manager.id, anonymous=False)

    rows = client.get("/api/v1/portal/manager/team", headers=manager_auth_headers).json()
    assert rows[0]["open_tickets"] == 1


def test_manager_summary_excludes_anonymous_tickets(
    client, manager_auth_headers, db, report_of_manager
):
    _add_ticket(db, report_of_manager.id, anonymous=True)
    _add_ticket(db, report_of_manager.id, anonymous=False)

    response = client.get("/api/v1/portal/manager/summary", headers=manager_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["open_team_tickets"] == 1


def test_manager_still_sees_their_own_leave(
    client, manager_auth_headers, db, report_of_manager, manager_user
):
    """Having a direct report must not hide a manager's own leave from them."""
    from datetime import date, timedelta

    from app.models.leave_request import LeaveRequest, LeaveStatus, LeaveType

    start = date.today() + timedelta(days=5)
    db.add(
        LeaveRequest(
            user_id=manager_user.id,
            start_date=start,
            end_date=start + timedelta(days=1),
            leave_type=LeaveType.paid,
            reason="Family trip",
            status=LeaveStatus.pending,
        )
    )
    db.commit()

    rows = client.get("/api/v1/leave", headers=manager_auth_headers).json()
    assert str(manager_user.id) in [r["user_id"] for r in rows]


def test_hr_still_sees_anonymous_tickets_without_the_author(
    client, hr_auth_headers, db, test_user
):
    """HR must still be able to act on it — anonymity hides who, not what."""
    _add_ticket(db, test_user.id, anonymous=True)

    response = client.get("/api/v1/tickets", headers=hr_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    rows = response.json()
    anon = [r for r in rows if r.get("is_anonymous")]
    assert anon, "HR lost sight of the anonymous ticket entirely"
    assert anon[0]["user_id"] is None, "anonymous ticket leaked its author to HR"
