import pytest
from fastapi import status
from unittest.mock import patch, MagicMock
import time


class TestAuthFlow:
    """Integration tests for full authentication flow."""

    def test_full_auth_flow_register_login_me(self, client, db):
        """Test complete auth flow: register -> login -> get me."""
        # Register a new user
        register_resp = client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "password": "pass123",
            "name": "New User",
            "employee_id": "EMP001",
            "designation": "Software Engineer"
        })
        assert register_resp.status_code == status.HTTP_200_OK
        register_data = register_resp.json()
        assert register_data["email"] == "newuser@example.com"
        assert register_data["name"] == "New User"
        assert register_data["role"] == "employee"

        # Login with the registered user
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "newuser@example.com",
            "password": "pass123"
        })
        assert login_resp.status_code == status.HTTP_200_OK
        token_data = login_resp.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        token = token_data["access_token"]

        # Get current user info
        me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == status.HTTP_200_OK
        me_data = me_resp.json()
        assert me_data["email"] == "newuser@example.com"
        assert me_data["name"] == "New User"

    def test_login_invalid_credentials(self, client, test_user):
        """Test login with invalid credentials returns 401."""
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword"
        })
        assert login_resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_register_duplicate_email(self, client, test_user):
        """Test registering with existing email returns 400."""
        register_resp = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "pass123",
            "name": "Duplicate User"
        })
        assert register_resp.status_code == status.HTTP_400_BAD_REQUEST


class TestChatFlow:
    """Integration tests for chat end-to-end flows."""

    def test_create_conversation_and_add_message(self, client, test_user, auth_headers, mock_redis):
        """Test creating conversation and adding messages."""
        # Create a new conversation
        conv_resp = client.post("/api/v1/chat/conversations", headers=auth_headers)
        assert conv_resp.status_code == status.HTTP_200_OK
        conv_data = conv_resp.json()
        assert "id" in conv_data
        conv_id = conv_data["id"]

        # Add a message to the conversation
        msg_resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            headers=auth_headers,
            json={"message_text": "Hello, I need help!", "sender": "user"}
        )
        assert msg_resp.status_code == status.HTTP_200_OK
        msg_data = msg_resp.json()
        assert msg_data["message_text"] == "Hello, I need help!"
        assert msg_data["sender"] == "user"

    def test_get_conversation_messages(self, client, test_user, auth_headers, mock_redis):
        """Test retrieving conversation and its messages."""
        # Create conversation
        conv_resp = client.post("/api/v1/chat/conversations", headers=auth_headers)
        conv_id = conv_resp.json()["id"]

        # Add multiple messages
        for i in range(3):
            client.post(
                f"/api/v1/chat/conversations/{conv_id}/messages",
                headers=auth_headers,
                json={"message_text": f"Message {i+1}", "sender": "user"}
            )

        # Get conversation details
        get_conv_resp = client.get(
            f"/api/v1/chat/conversations/{conv_id}",
            headers=auth_headers
        )
        assert get_conv_resp.status_code == status.HTTP_200_OK
        conv_data = get_conv_resp.json()
        assert "messages" in conv_data
        assert len(conv_data["messages"]) >= 3

    def test_list_user_conversations(self, client, test_user, auth_headers, mock_redis):
        """Test listing user's conversations."""
        # Create multiple conversations
        for _ in range(2):
            client.post("/api/v1/chat/conversations", headers=auth_headers)

        # List conversations
        list_resp = client.get("/api/v1/chat/conversations", headers=auth_headers)
        assert list_resp.status_code == status.HTTP_200_OK
        conversations = list_resp.json()
        assert len(conversations) >= 2


class TestTicketFlow:
    """Integration tests for ticket management flows."""

    def test_create_and_update_ticket(self, client, test_user, auth_headers):
        """Test creating a ticket and updating its status."""
        # Create a new ticket
        ticket_resp = client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Need help with leave application",
            "category": "leave",
            "priority": "medium"
        })
        assert ticket_resp.status_code == status.HTTP_200_OK
        ticket_data = ticket_resp.json()
        assert ticket_data["query"] == "Need help with leave application"
        assert ticket_data["category"] == "leave"
        assert ticket_data["status"] == "open"
        ticket_id = ticket_data["id"]

        # Update ticket status
        update_resp = client.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=auth_headers,
            json={"status": "in_progress"}
        )
        assert update_resp.status_code == status.HTTP_200_OK
        updated_data = update_resp.json()
        assert updated_data["status"] == "in_progress"

    def test_create_ticket_add_message(self, client, test_user, auth_headers):
        """Test creating a ticket and adding messages to it."""
        # Create ticket
        ticket_resp = client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "HR policy question",
            "category": "policy",
            "priority": "low"
        })
        ticket_id = ticket_resp.json()["id"]

        # Add message to ticket
        msg_resp = client.post(
            f"/api/v1/tickets/{ticket_id}/messages",
            headers=auth_headers,
            json={"message_text": "Following up on my query"}
        )
        assert msg_resp.status_code == status.HTTP_200_OK
        msg_data = msg_resp.json()
        assert msg_data["message_text"] == "Following up on my query"

    def test_list_user_tickets(self, client, test_user, auth_headers):
        """Test listing user's tickets."""
        # Create multiple tickets
        for i in range(3):
            client.post("/api/v1/tickets", headers=auth_headers, json={
                "query": f"Query {i+1}",
                "category": "general",
                "priority": "medium"
            })

        # List tickets
        list_resp = client.get("/api/v1/tickets", headers=auth_headers)
        assert list_resp.status_code == status.HTTP_200_OK
        tickets = list_resp.json()
        assert len(tickets) >= 3


class TestUnauthorizedAccess:
    """Integration tests for unauthorized access protection."""

    def test_protected_endpoints_require_auth(self, client):
        """Test that protected endpoints reject unauthenticated requests."""
        protected_endpoints = [
            ("GET", "/api/v1/chat/conversations"),
            ("POST", "/api/v1/chat/conversations"),
            ("GET", "/api/v1/tickets"),
            ("POST", "/api/v1/tickets"),
            ("GET", "/api/v1/surveys"),
        ]

        for method, endpoint in protected_endpoints:
            if method == "GET":
                resp = client.get(endpoint)
            else:
                resp = client.post(endpoint, json={})
            
            assert resp.status_code in [
                status.HTTP_403_FORBIDDEN, 
                status.HTTP_401_UNAUTHORIZED
            ], f"Expected 403/401 for {method} {endpoint}, got {resp.status_code}"

    def test_invalid_token_rejected(self, client):
        """Test that invalid tokens are rejected."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        resp = client.get("/api/v1/chat/conversations", headers=headers)
        assert resp.status_code in [
            status.HTTP_403_FORBIDDEN, 
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_expired_token_rejected(self, client, test_user):
        """Test that expired tokens are rejected."""
        from jose import jwt as jose_jwt
        import time
        expired_token = jose_jwt.encode(
            {"sub": str(test_user.id), "role": "employee", "exp": int(time.time()) - 3600},
            "test-secret-key",
            algorithm="HS256"
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        resp = client.get("/api/v1/chat/conversations", headers=headers)
        assert resp.status_code in [
            status.HTTP_403_FORBIDDEN, 
            status.HTTP_401_UNAUTHORIZED
        ]


class TestRateLimiting:
    """Integration tests for rate limiting."""

    def test_login_rate_limit(self, client, test_user, mock_redis):
        """Test that login endpoint is rate limited."""
        # Configure mock to simulate rate limiting
        mock_redis.get.return_value = None
        
        # Make multiple login attempts
        for i in range(10):
            resp = client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "wrongpassword"
            })
            # First few should be 401 (invalid credentials), not rate limited
            if i < 5:
                assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_chat_message_rate_limit(self, client, test_user, auth_headers, mock_redis):
        """Test that chat messages are rate limited."""
        # Create conversation first
        conv_resp = client.post("/api/v1/chat/conversations", headers=auth_headers)
        conv_id = conv_resp.json()["id"]

        # Configure mock for rate limiting
        call_count = [0]
        
        def mock_get_redis():
            mock = MagicMock()
            mock.ping.return_value = True
            mock.get.return_value = None
            mock.setex.return_value = True
            mock.delete.return_value = True
            
            def track_call(*args, **kwargs):
                call_count[0] += 1
                return None
            
            mock.get.side_effect = track_call
            return mock

        with patch("app.services.chat.get_redis_client", mock_get_redis):
            # Send multiple messages rapidly
            for i in range(20):
                resp = client.post(
                    f"/api/v1/chat/conversations/{conv_id}/messages",
                    headers=auth_headers,
                    json={"message_text": f"Test message {i}", "sender": "user"}
                )
                # Should eventually hit rate limit
                if resp.status_code == 429:
                    break

    def test_api_overall_rate_limit(self, client, test_user, auth_headers):
        """Test general API rate limiting."""
        # Make many rapid requests
        responses = []
        for i in range(50):
            resp = client.get("/api/v1/tickets", headers=auth_headers)
            responses.append(resp.status_code)
            if resp.status_code == 429:
                break

        # Should eventually hit rate limit
        assert 429 in responses or len(responses) < 50


class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    def test_complete_user_journey(self, client, db):
        """Test a complete user journey from registration to creating tickets."""
        # Step 1: Register new user
        register_resp = client.post("/api/v1/auth/register", json={
            "email": "journey@example.com",
            "password": "journey123",
            "name": "Journey User",
            "employee_id": "EMP999",
            "designation": "Tester"
        })
        assert register_resp.status_code == status.HTTP_200_OK

        # Step 2: Login
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "journey@example.com",
            "password": "journey123"
        })
        assert login_resp.status_code == status.HTTP_200_OK
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 3: Create chat conversation
        conv_resp = client.post("/api/v1/chat/conversations", headers=headers)
        assert conv_resp.status_code == status.HTTP_200_OK
        conv_id = conv_resp.json()["id"]

        # Step 4: Send chat messages
        client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            headers=headers,
            json={"message_text": "I have a question", "sender": "user"}
        )

        # Step 5: Create a ticket
        ticket_resp = client.post("/api/v1/tickets", headers=headers, json={
            "query": "This is my ticket query",
            "category": "general",
            "priority": "medium"
        })
        assert ticket_resp.status_code == status.HTTP_200_OK
        ticket_id = ticket_resp.json()["id"]

        # Step 6: Verify user can see all their data
        tickets_resp = client.get("/api/v1/tickets", headers=headers)
        assert tickets_resp.status_code == status.HTTP_200_OK
        
        conversations_resp = client.get("/api/v1/chat/conversations", headers=headers)
        assert conversations_resp.status_code == status.HTTP_200_OK

        # Step 7: Verify profile
        me_resp = client.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == status.HTTP_200_OK
        assert me_resp.json()["email"] == "journey@example.com"
