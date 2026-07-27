"""End-to-end coverage for the conversational employee-request flows.

Each flow is driven the way an employee would drive it — one chat message at a
time — and asserted against the row it is supposed to leave behind, so a broken
slot loop fails here rather than in production.
"""

from datetime import date, timedelta

import pytest
from fastapi import status

from app.models.employee_request import EmployeeRequest, RequestStatus, RequestType


class Conversation:
    """Threads conversation_id across turns — without it the endpoint starts a
    fresh conversation each message and flow state never survives a turn."""

    def __init__(self, client, headers):
        self.client = client
        self.headers = headers
        self.conversation_id = None

    def say(self, message):
        payload = {"message": message}
        if self.conversation_id:
            payload["conversation_id"] = str(self.conversation_id)
        response = self.client.post(
            "/api/v1/chat/message", headers=self.headers, json=payload
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        self.conversation_id = body["conversation_id"]
        return body


@pytest.fixture
def chat(client, auth_headers):
    return Conversation(client, auth_headers)


def _say(client, headers, message):
    """Single-turn helper for the routing assertions."""
    return Conversation(client, headers).say(message)


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# --------------------------------------------------------------------------- #
# Intent routing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "message,expected_flow",
    [
        ("I want to book an appointment with HR", "appointment_request"),
        ("I need to file a reimbursement", "expense_claim"),
        ("I need a shift change next week", "shift_change_request"),
        ("Can I get my payslip?", "document_request"),
    ],
)
def test_message_starts_expected_flow(client, auth_headers, message, expected_flow):
    payload = _say(client, auth_headers, message)
    assert payload["flow_metadata"]["flow_name"] == expected_flow
    assert payload["flow_metadata"]["completed"] is False


def test_leave_request_still_wins_over_shift_change(client, auth_headers):
    """"apply for leave" must keep routing to the leave flow, not shift change."""
    payload = _say(client, auth_headers, "I want to apply for leave")
    assert payload["flow_metadata"]["flow_name"] == "leave_request"


@pytest.mark.parametrize(
    "message",
    [
        "book a meeting room at 3 pm",
        "schedule a meeting with rahul",
    ],
)
def test_appointment_flow_does_not_hijack_room_or_calendar_booking(
    client, auth_headers, message
):
    """The productivity agent owns generic room/meeting booking.

    The appointment flow only claims the word "appointment" or an explicit HR
    counterpart — a greedier pattern silently swallowed both of these.
    """
    payload = _say(client, auth_headers, message)
    assert payload["flow_metadata"]["flow_name"] != "appointment_request"


# --------------------------------------------------------------------------- #
# Full flows
# --------------------------------------------------------------------------- #


def test_document_request_flow_creates_row(chat, db, test_user):
    chat.say("Can I get my payslip?")
    chat.say("I need it for a home loan application")
    final = chat.say("yes")

    row = (
        db.query(EmployeeRequest)
        .filter(EmployeeRequest.user_id == test_user.id)
        .one()
    )
    assert row.request_type == RequestType.document
    assert row.status == RequestStatus.pending
    assert row.details["document_type"] == "payslip"
    assert "loan" in row.details["purpose"].lower()
    assert "hr" in final["response"].lower() or "requested" in final["response"].lower()


def test_opening_phrase_is_not_captured_as_the_topic(chat, db, test_user):
    """The phrase that starts a flow must not answer its first question.

    Otherwise HR reads "1:1 with HR - i want to book an appointment with hr"
    instead of why the employee actually wants to talk.
    """
    first = chat.say("I want to book an appointment with HR")
    assert "talk about" in first["response"].lower(), first["response"]
    assert first["flow_metadata"]["collected_fields"] == []

    # Finish the flow so the stored topic can be inspected.
    chat.say("My workload has been unmanageable since the reorg")
    chat.say(_future(3))
    chat.say("11:00")
    chat.say("video")
    chat.say("yes")

    row = db.query(EmployeeRequest).filter(EmployeeRequest.user_id == test_user.id).one()
    assert row.details["topic"] == "My workload has been unmanageable since the reorg"
    assert "unmanageable" in row.title


def test_appointment_flow_sets_scheduled_at(chat, db, test_user):
    day = _future(3)
    chat.say("I want to book an appointment with HR")
    chat.say("I'd like to discuss my career growth")
    chat.say(day)
    chat.say("3pm")
    chat.say("video")
    chat.say("yes")

    row = (
        db.query(EmployeeRequest)
        .filter(EmployeeRequest.user_id == test_user.id)
        .one()
    )
    assert row.request_type == RequestType.appointment
    assert row.details["preferred_time"] == "15:00"
    assert row.scheduled_at is not None
    assert row.scheduled_at.date().isoformat() == day
    assert row.scheduled_at.hour == 15


def test_expense_flow_parses_amount(chat, db, test_user):
    chat.say("I need to file a reimbursement")
    chat.say("travel")
    chat.say("2,500")
    chat.say(_future(-2))
    chat.say("Cab fare to the client office")
    chat.say("yes")

    row = (
        db.query(EmployeeRequest)
        .filter(EmployeeRequest.user_id == test_user.id)
        .one()
    )
    assert row.request_type == RequestType.expense
    assert float(row.amount) == 2500.0
    assert row.details["expense_type"] == "travel"


def test_shift_change_flow_records_date_range(chat, db, test_user):
    """The opening message names the type, so the flow must not re-ask for it."""
    start, end = _future(5), _future(7)
    chat.say("I need a shift change next week")
    chat.say(start)
    chat.say(end)
    chat.say("Covering for a teammate on the early roster")
    chat.say("yes")

    row = (
        db.query(EmployeeRequest)
        .filter(EmployeeRequest.user_id == test_user.id)
        .one()
    )
    assert row.request_type == RequestType.shift_change
    assert row.start_date.isoformat() == start
    assert row.end_date.isoformat() == end
    assert row.details["change_type"] == "shift change"


def test_wfh_request_is_a_shift_change_not_leave(chat, db, test_user):
    start = _future(4)
    chat.say("Can I work from home on Friday?")
    chat.say(start)
    chat.say(start)
    chat.say("Plumber visit at home")
    chat.say("yes")

    row = (
        db.query(EmployeeRequest)
        .filter(EmployeeRequest.user_id == test_user.id)
        .one()
    )
    assert row.request_type == RequestType.shift_change
    assert row.details["change_type"] == "work from home"


def test_declining_confirmation_does_not_create_row(chat, db, test_user):
    chat.say("Can I get my payslip?")
    chat.say("For a visa application")
    chat.say("no")

    assert db.query(EmployeeRequest).filter(EmployeeRequest.user_id == test_user.id).count() == 0


def test_invalid_time_is_re_asked(chat, db, test_user):
    chat.say("I want to book an appointment with HR")
    chat.say("Discuss my role")
    chat.say(_future(2))
    payload = chat.say("sometime in the afternoon maybe")

    # The flow must still be waiting on a readable time, not have moved on.
    assert payload["flow_metadata"]["flow_name"] == "appointment_request"
    assert "preferred_time" in payload["flow_metadata"]["missing_fields"]
    assert db.query(EmployeeRequest).count() == 0


# --------------------------------------------------------------------------- #
# HR review API
# --------------------------------------------------------------------------- #


@pytest.fixture
def pending_request(db, test_user):
    row = EmployeeRequest(
        user_id=test_user.id,
        request_type=RequestType.document,
        status=RequestStatus.pending,
        title="Payslip request",
        details={"document_type": "payslip", "purpose": "loan"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_employee_sees_only_their_own_requests(client, auth_headers, pending_request):
    response = client.get("/api/v1/requests", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["id"] == str(pending_request.id)
    assert rows[0]["employee_name"] == "Test User"


def test_hr_can_approve(client, hr_auth_headers, pending_request, db, hr_user):
    response = client.patch(
        f"/api/v1/requests/{pending_request.id}/approve",
        headers=hr_auth_headers,
        json={"hr_note": "Sent to payroll"},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "approved"
    assert body["hr_note"] == "Sent to payroll"
    assert body["handled_by"] == str(hr_user.id)


def test_employee_cannot_approve_own_request(client, auth_headers, pending_request):
    response = client.patch(
        f"/api/v1/requests/{pending_request.id}/approve",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_already_actioned_request_cannot_be_actioned_again(
    client, hr_auth_headers, pending_request
):
    first = client.patch(
        f"/api/v1/requests/{pending_request.id}/reject",
        headers=hr_auth_headers,
        json={"hr_note": "Not eligible"},
    )
    assert first.status_code == status.HTTP_200_OK

    second = client.patch(
        f"/api/v1/requests/{pending_request.id}/approve",
        headers=hr_auth_headers,
        json={},
    )
    assert second.status_code == status.HTTP_400_BAD_REQUEST


def test_schedule_rejects_non_appointment(client, hr_auth_headers, pending_request):
    response = client.patch(
        f"/api/v1/requests/{pending_request.id}/schedule",
        headers=hr_auth_headers,
        json={"scheduled_at": "2030-01-01T10:00:00"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_hr_can_schedule_appointment(client, hr_auth_headers, db, test_user):
    row = EmployeeRequest(
        user_id=test_user.id,
        request_type=RequestType.appointment,
        status=RequestStatus.pending,
        title="1:1 with HR",
        details={"topic": "career growth"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    response = client.patch(
        f"/api/v1/requests/{row.id}/schedule",
        headers=hr_auth_headers,
        json={"scheduled_at": "2030-01-01T10:00:00", "hr_note": "Confirmed"},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["scheduled_at"].startswith("2030-01-01T10:00")


def test_employee_can_cancel_own_request(client, auth_headers, pending_request):
    response = client.patch(
        f"/api/v1/requests/{pending_request.id}/cancel", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "cancelled"


def _employee_chat_messages(db, user_id):
    from app.models.conversation import Conversation, Message, MessageSender

    return (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id, Message.sender == MessageSender.bot)
        .all()
    )


def test_approval_tells_the_employee_in_chat(
    client, hr_auth_headers, pending_request, db, test_user
):
    """HR actioning a request must close the loop — silence is the old behaviour."""
    client.patch(
        f"/api/v1/requests/{pending_request.id}/approve",
        headers=hr_auth_headers,
        json={"hr_note": "Sent to payroll"},
    )

    messages = _employee_chat_messages(db, test_user.id)
    assert messages, "employee was never told their request was approved"
    text = " ".join(m.message_text.lower() for m in messages)
    assert "approved" in text
    assert "sent to payroll" in text


def test_rejection_tells_the_employee_in_chat(
    client, hr_auth_headers, pending_request, db, test_user
):
    client.patch(
        f"/api/v1/requests/{pending_request.id}/reject",
        headers=hr_auth_headers,
        json={"hr_note": "Not eligible yet"},
    )

    text = " ".join(m.message_text.lower() for m in _employee_chat_messages(db, test_user.id))
    assert "couldn't approve" in text
    assert "not eligible yet" in text


def test_scheduling_tells_the_employee_the_slot(client, hr_auth_headers, db, test_user):
    row = EmployeeRequest(
        user_id=test_user.id,
        request_type=RequestType.appointment,
        status=RequestStatus.pending,
        title="1:1 with HR",
        details={"topic": "career growth"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    client.patch(
        f"/api/v1/requests/{row.id}/schedule",
        headers=hr_auth_headers,
        json={"scheduled_at": "2030-01-01T10:00:00"},
    )

    text = " ".join(m.message_text.lower() for m in _employee_chat_messages(db, test_user.id))
    assert "confirmed" in text
    assert "01 jan at 10:00" in text


def test_employee_cancelling_does_not_notify_themselves(
    client, auth_headers, pending_request, db, test_user
):
    """Withdrawing your own request shouldn't send you a message about it."""
    client.patch(f"/api/v1/requests/{pending_request.id}/cancel", headers=auth_headers)
    assert _employee_chat_messages(db, test_user.id) == []


# --------------------------------------------------------------------------- #
# Manager review path — shift changes are approved in line, not by HR
# --------------------------------------------------------------------------- #


@pytest.fixture
def report_of_manager(db, test_user, manager_user):
    test_user.manager_id = manager_user.id
    db.commit()
    return test_user


@pytest.fixture
def report_shift_change(db, report_of_manager):
    row = EmployeeRequest(
        user_id=report_of_manager.id,
        request_type=RequestType.shift_change,
        status=RequestStatus.pending,
        title="Work from home request",
        details={"change_type": "work from home", "reason": "plumber"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_manager_can_action_a_direct_reports_shift_change(
    client, manager_auth_headers, report_shift_change, manager_user
):
    response = client.patch(
        f"/api/v1/requests/{report_shift_change.id}/approve",
        headers=manager_auth_headers,
        json={"hr_note": "Fine by me"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["handled_by"] == str(manager_user.id)


# --------------------------------------------------------------------------- #
# Confidentiality: a manager must not see what an employee took to HR
# --------------------------------------------------------------------------- #


@pytest.fixture
def confidential_appointment(db, report_of_manager):
    """The exact case the product exists for: escalating about your own manager."""
    row = EmployeeRequest(
        user_id=report_of_manager.id,
        request_type=RequestType.appointment,
        status=RequestStatus.pending,
        title="1:1 with HR — my manager keeps overriding me in public",
        details={"topic": "my manager keeps overriding me in public"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_manager_cannot_see_a_reports_hr_appointment(
    client, manager_auth_headers, confidential_appointment
):
    listed = client.get("/api/v1/requests", headers=manager_auth_headers).json()
    assert [r["id"] for r in listed] == []

    direct = client.get(
        f"/api/v1/requests/{confidential_appointment.id}", headers=manager_auth_headers
    )
    assert direct.status_code == status.HTTP_404_NOT_FOUND


def test_manager_cannot_action_a_reports_hr_appointment(
    client, manager_auth_headers, confidential_appointment
):
    response = client.patch(
        f"/api/v1/requests/{confidential_appointment.id}/approve",
        headers=manager_auth_headers,
        json={},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_manager_cannot_see_a_reports_document_request(
    client, manager_auth_headers, db, report_of_manager
):
    """An experience-letter request tells the manager their report is leaving."""
    row = EmployeeRequest(
        user_id=report_of_manager.id,
        request_type=RequestType.document,
        status=RequestStatus.pending,
        title="Experience letter request",
        details={"document_type": "experience letter", "purpose": "new job"},
    )
    db.add(row)
    db.commit()

    listed = client.get("/api/v1/requests", headers=manager_auth_headers).json()
    assert listed == []


def test_hr_still_sees_confidential_appointments(
    client, hr_auth_headers, confidential_appointment
):
    listed = client.get("/api/v1/requests", headers=hr_auth_headers).json()
    assert [r["id"] for r in listed] == [str(confidential_appointment.id)]


def test_employee_still_sees_their_own_confidential_request(
    client, auth_headers, confidential_appointment
):
    listed = client.get("/api/v1/requests", headers=auth_headers).json()
    assert [r["id"] for r in listed] == [str(confidential_appointment.id)]


def test_manager_cannot_action_a_reviewable_type_for_a_non_report(
    client, manager_auth_headers, db, test_user
):
    """A shift change is a manager-reviewable type, but only for their own reports."""
    assert test_user.manager_id is None
    row = EmployeeRequest(
        user_id=test_user.id,
        request_type=RequestType.shift_change,
        status=RequestStatus.pending,
        title="Shift change request",
        details={"change_type": "shift change"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    response = client.patch(
        f"/api/v1/requests/{row.id}/approve", headers=manager_auth_headers, json={}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_manager_sees_direct_reports_shift_changes(
    client, manager_auth_headers, report_shift_change
):
    response = client.get("/api/v1/requests", headers=manager_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert [row["id"] for row in response.json()] == [str(report_shift_change.id)]


def test_manager_without_reports_sees_nothing(
    client, manager_auth_headers, pending_request, test_user
):
    assert test_user.manager_id is None
    response = client.get("/api/v1/requests", headers=manager_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_summary_counts_by_status_and_type(client, hr_auth_headers, pending_request):
    response = client.get("/api/v1/requests/summary", headers=hr_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["pending"] == 1
    assert body["by_type"]["document"] == 1
