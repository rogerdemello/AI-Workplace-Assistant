import uuid

from app.auth import create_access_token, hash_password
from app.models.user import User, UserRole, UserStatus


def _auth_headers_for(user_id: uuid.UUID, role: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id), "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_manager_dashboard_bundle_returns_team_aggregate(client, db):
    manager = User(
        id=uuid.uuid4(),
        email="mgr-dash@example.com",
        name="Manager Dash",
        hashed_password=hash_password("manager123"),
        role=UserRole.manager,
        status=UserStatus.active,
    )
    report = User(
        id=uuid.uuid4(),
        email="report-dash@example.com",
        name="Report Dash",
        hashed_password=hash_password("report123"),
        role=UserRole.employee,
        status=UserStatus.active,
        manager_id=manager.id,
    )
    db.add_all([manager, report])
    db.commit()

    headers = _auth_headers_for(manager.id, "manager")
    response = client.get("/api/v1/analytics/manager/dashboard", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["manager_id"] == str(manager.id)
    assert payload["team_size"] >= 1
    assert "avg_team_sentiment" in payload
    assert "avg_team_risk" in payload
    assert isinstance(payload["employees"], list)


def test_hr_cannot_view_manager_dashboard_bundle(client, hr_auth_headers):
    response = client.get("/api/v1/analytics/manager/dashboard", headers=hr_auth_headers)
    assert response.status_code == 403
