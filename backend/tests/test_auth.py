import pytest
from fastapi import status


class TestUserRegistration:
    """Tests for user registration endpoint."""

    def test_register_user_success(self, client):
        """Test successful user registration."""
        response = client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "password": "password123",
            "name": "New User",
            "employee_id": "EMP001",
            "designation": "Software Engineer"
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "New User"
        assert data["role"] == "employee"
        assert "id" in data

    def test_register_user_with_minimal_fields(self, client):
        """Test user registration with only required fields."""
        response = client.post("/api/v1/auth/register", json={
            "email": "minimal@example.com",
            "password": "password123",
            "name": "Minimal User"
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "minimal@example.com"
        assert data["name"] == "Minimal User"

    def test_register_user_duplicate_email(self, client, test_user):
        """Test that duplicate email registration fails."""
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "password123",
            "name": "Duplicate User"
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email already registered" in response.json()["detail"]

    def test_register_user_invalid_email(self, client):
        """Test that invalid email format is rejected."""
        response = client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "password123",
            "name": "Invalid User"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestUserLogin:
    """Tests for user login endpoint."""

    def test_login_success(self, client, test_user):
        """Test successful login with valid credentials."""
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123"
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_email(self, client, test_user):
        """Test login with non-existent email."""
        response = client.post("/api/v1/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password123"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_invalid_password(self, client, test_user):
        """Test login with incorrect password."""
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_empty_credentials(self, client):
        """Test login with empty credentials."""
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetCurrentUser:
    """Tests for getting current user endpoint."""

    def test_get_current_user_success(self, client, test_user, auth_headers):
        """Test getting current user with valid token."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == test_user.email
        assert data["name"] == test_user.name

    def test_get_current_user_no_token(self, client):
        """Test getting current user without token."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestTokenValidation:
    """Tests for token validation and JWT functionality."""

    def test_token_contains_user_id(self, client, test_user):
        """Test that login token contains user ID."""
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123"
        })
        data = response.json()
        token = data["access_token"]
        
        # Verify token can be used to access protected endpoint
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == status.HTTP_200_OK
        assert me_response.json()["id"] == str(test_user.id)

    def test_token_contains_role(self, client, test_user):
        """Test that login token contains user role."""
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123"
        })
        data = response.json()
        token = data["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get("/api/v1/auth/me", headers=headers)
        assert me_response.json()["role"] == "employee"
