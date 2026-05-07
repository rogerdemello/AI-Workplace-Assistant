import uuid

from fastapi import status

from app.auth import create_access_token


def test_hr_role_can_access_hr_protected_route(client, hr_auth_headers):
    response = client.get("/api/v1/analytics/dashboard", headers=hr_auth_headers)
    assert response.status_code == status.HTTP_200_OK


def test_admin_role_can_access_admin_protected_route(client, admin_auth_headers):
    response = client.get("/api/v1/analytics/attrition", headers=admin_auth_headers)
    assert response.status_code == status.HTTP_200_OK


def test_employee_role_is_denied_for_hr_protected_route(client, auth_headers):
    response = client.get("/api/v1/analytics/dashboard", headers=auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Insufficient permissions"


def test_token_for_unknown_user_is_rejected(client):
    token = create_access_token(data={"sub": str(uuid.uuid4()), "role": "employee"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "User not found for the provided token"
