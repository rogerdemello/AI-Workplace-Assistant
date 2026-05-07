import uuid
from datetime import date
from unittest.mock import MagicMock, patch

from app.auth import create_access_token, hash_password
from app.models.leave_request import LeaveRequest, LeaveStatus, LeaveType
from app.models.hr_notification import HrNotification
from app.models.user import User, UserRole, UserStatus


def _auth_headers_for(user_id: uuid.UUID, role: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id), "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_portal_timeline_includes_leave_events(client, db, test_user, auth_headers):
    leave = LeaveRequest(
        user_id=test_user.id,
        start_date=date.today(),
        end_date=date.today(),
        leave_type=LeaveType.paid,
        status=LeaveStatus.approved,
    )
    db.add(leave)
    db.commit()

    response = client.get("/api/v1/portal/me/timeline", headers=auth_headers)

    assert response.status_code == 200
    timeline = response.json()
    assert any("Leave (" in item["text"] for item in timeline)


def test_manager_team_shows_leave_balance(client, db):
    manager = User(
        id=uuid.uuid4(),
        email="manager@example.com",
        name="Manager User",
        hashed_password=hash_password("managerpass123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    report = User(
        id=uuid.uuid4(),
        email="report@example.com",
        name="Report User",
        hashed_password=hash_password("reportpass123"),
        role=UserRole.employee,
        status=UserStatus.active,
        manager_id=manager.id,
    )
    db.add(manager)
    db.add(report)
    db.commit()

    db.add(
        LeaveRequest(
            user_id=report.id,
            start_date=date(date.today().year, 1, 5),
            end_date=date(date.today().year, 1, 6),
            leave_type=LeaveType.paid,
            status=LeaveStatus.approved,
        )
    )
    db.commit()

    headers = _auth_headers_for(manager.id, "employee")
    response = client.get("/api/v1/portal/manager/team", headers=headers)

    assert response.status_code == 200
    team = response.json()
    report_row = next(row for row in team if row["id"] == str(report.id))
    assert report_row["leave_balance"] == 23


def test_send_email_endpoint_uses_smtp(client, auth_headers, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "mailer@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test-pass")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "mailer@example.com")
    monkeypatch.setenv("SMTP_USE_TLS", "true")

    smtp_mock = MagicMock()
    smtp_context = MagicMock()
    smtp_context.__enter__.return_value = smtp_mock
    smtp_context.__exit__.return_value = False

    with patch("app.services.email_sender.smtplib.SMTP", return_value=smtp_context):
        response = client.post(
            "/api/v1/email/send",
            headers=auth_headers,
            json={
                "to": "recipient@example.com",
                "subject": "Hello",
                "body": "This is a test",
                "cc": ["cc@example.com"],
            },
        )

    assert response.status_code == 200
    assert "Email sent" in response.json()["detail"]
    assert smtp_mock.starttls.called
    assert smtp_mock.send_message.called


def test_hr_notifications_list_and_mark_read(client, db, hr_user):
    db.add(
        HrNotification(
            ticket_id=None,
            actor_id=hr_user.id,
            title="Escalation detected",
            body="Ticket escalated by workflow",
            notification_type="ticket_escalated",
            severity="high",
        )
    )
    db.commit()

    headers = _auth_headers_for(hr_user.id, "hr")
    list_response = client.get("/api/v1/portal/hr/notifications", headers=headers)
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) >= 1
    first = rows[0]
    assert first["title"]

    mark_response = client.post(f"/api/v1/portal/hr/notifications/{first['id']}/read", headers=headers)
    assert mark_response.status_code == 200
    assert mark_response.json()["ok"] is True


def test_employee_cannot_access_hr_notifications(client, auth_headers):
    list_response = client.get("/api/v1/portal/hr/notifications", headers=auth_headers)
    assert list_response.status_code == 403
