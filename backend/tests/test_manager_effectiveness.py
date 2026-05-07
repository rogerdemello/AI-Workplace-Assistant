import uuid

from app.auth import create_access_token, hash_password
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.user import User, UserRole, UserStatus


def _auth_headers_for(user_id: uuid.UUID, role: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id), "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_hr_can_view_manager_effectiveness(client, db):
    manager = User(
        id=uuid.uuid4(),
        email="mgr-effect@example.com",
        name="Manager Effect",
        hashed_password=hash_password("manager123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    report = User(
        id=uuid.uuid4(),
        email="report-effect@example.com",
        name="Report Effect",
        hashed_password=hash_password("report123"),
        role=UserRole.employee,
        status=UserStatus.active,
        manager_id=manager.id,
    )
    hr = User(
        id=uuid.uuid4(),
        email="hr-effect@example.com",
        name="HR Effect",
        hashed_password=hash_password("hr123"),
        role=UserRole.hr,
        status=UserStatus.active,
    )
    db.add_all([manager, report, hr])
    db.commit()

    db.add(
        Ticket(
            user_id=report.id,
            query="Manager conflict issue",
            category="complaint",
            priority=TicketPriority.high,
            status=TicketStatus.open,
        )
    )
    db.commit()

    headers = _auth_headers_for(hr.id, "hr")
    response = client.get("/api/v1/analytics/manager-effectiveness", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    assert any(row["manager_id"] == str(manager.id) for row in rows)


def test_employee_cannot_view_manager_effectiveness(client, auth_headers):
    response = client.get("/api/v1/analytics/manager-effectiveness", headers=auth_headers)
    assert response.status_code == 403
