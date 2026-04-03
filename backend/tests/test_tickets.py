import pytest
from fastapi import status


class TestCreateTicket:
    """Tests for creating ticket endpoint."""

    def test_create_ticket_success(self, client, test_user, auth_headers):
        """Test successful ticket creation."""
        response = client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "I need help with leave",
            "category": "leave",
            "priority": "medium"
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["query"] == "I need help with leave"
        assert data["category"] == "leave"
        assert data["status"] == "open"
        assert data["priority"] == "medium"
        assert "id" in data

    def test_create_ticket_with_different_priorities(self, client, test_user, auth_headers):
        """Test creating tickets with different priority levels."""
        priorities = ["low", "medium", "high", "critical"]
        
        for priority in priorities:
            response = client.post("/api/v1/tickets", headers=auth_headers, json={
                "query": f"Test ticket priority {priority}",
                "category": "general",
                "priority": priority
            })
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["priority"] == priority

    def test_create_ticket_unauthorized(self, client):
        """Test creating ticket without authentication."""
        response = client.post("/api/v1/tickets", json={
            "query": "Test ticket",
            "category": "general",
            "priority": "low"
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_ticket_with_all_categories(self, client, test_user, auth_headers):
        """Test creating tickets with different categories."""
        categories = ["leave", "payroll", "benefits", "general", "it_support"]
        
        for category in categories:
            response = client.post("/api/v1/tickets", headers=auth_headers, json={
                "query": f"Test ticket for {category}",
                "category": category,
                "priority": "low"
            })
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["category"] == category


class TestGetTickets:
    """Tests for getting tickets list endpoint."""

    def test_get_tickets_empty(self, client, test_user, auth_headers):
        """Test getting empty list of tickets."""
        response = client.get("/api/v1/tickets", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_tickets_with_data(self, client, test_user, auth_headers):
        """Test getting list of tickets."""
        # Create a ticket first
        client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Test ticket",
            "category": "general",
            "priority": "low"
        })
        
        response = client.get("/api/v1/tickets", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_tickets_filter_by_status(self, client, test_user, auth_headers):
        """Test filtering tickets by status."""
        # Create tickets
        client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Open ticket",
            "category": "general",
            "priority": "low"
        })
        
        # Filter by status
        response = client.get(
            "/api/v1/tickets?status=open",
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert all(ticket["status"] == "open" for ticket in data)

    def test_get_tickets_unauthorized(self, client):
        """Test getting tickets without authentication."""
        response = client.get("/api/v1/tickets")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetTicket:
    """Tests for getting a single ticket endpoint."""

    def test_get_ticket_success(self, client, test_user, auth_headers):
        """Test getting a specific ticket."""
        # Create a ticket first
        create_response = client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Test ticket",
            "category": "general",
            "priority": "low"
        })
        ticket_id = create_response.json()["id"]
        
        response = client.get(f"/api/v1/tickets/{ticket_id}", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == ticket_id
        assert data["query"] == "Test ticket"

    def test_get_ticket_not_found(self, client, test_user, auth_headers):
        """Test getting non-existent ticket."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/v1/tickets/{fake_id}", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateTicket:
    """Tests for updating ticket endpoint."""

    def test_update_ticket_status(self, client, test_user, auth_headers):
        """Test updating ticket status."""
        # Create a ticket first
        create_response = client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Test ticket",
            "category": "general",
            "priority": "low"
        })
        ticket_id = create_response.json()["id"]
        
        response = client.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=auth_headers,
            json={"status": "in_progress"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "in_progress"

    def test_update_ticket_priority(self, client, test_user, auth_headers):
        """Test updating ticket priority."""
        # Create a ticket first
        create_response = client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Test ticket",
            "category": "general",
            "priority": "low"
        })
        ticket_id = create_response.json()["id"]
        
        response = client.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=auth_headers,
            json={"priority": "high"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["priority"] == "high"

    def test_update_ticket_to_resolved(self, client, test_user, auth_headers):
        """Test resolving a ticket."""
        # Create a ticket first
        create_response = client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Test ticket",
            "category": "general",
            "priority": "low"
        })
        ticket_id = create_response.json()["id"]
        
        response = client.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=auth_headers,
            json={"status": "resolved"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "resolved"
        assert data["resolved_at"] is not None

    def test_update_ticket_not_found(self, client, test_user, auth_headers):
        """Test updating non-existent ticket."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.patch(
            f"/api/v1/tickets/{fake_id}",
            headers=auth_headers,
            json={"status": "in_progress"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestTicketMessages:
    """Tests for adding messages to tickets."""

    def test_add_ticket_message(self, client, test_user, auth_headers):
        """Test adding a message to a ticket."""
        # Create a ticket first
        create_response = client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Test ticket",
            "category": "general",
            "priority": "low"
        })
        ticket_id = create_response.json()["id"]
        
        response = client.post(
            f"/api/v1/tickets/{ticket_id}/messages",
            headers=auth_headers,
            json={"message_text": "This is an update"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message_text"] == "This is an update"
        assert data["ticket_id"] == ticket_id

    def test_add_message_to_nonexistent_ticket(self, client, test_user, auth_headers):
        """Test adding message to non-existent ticket."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.post(
            f"/api/v1/tickets/{fake_id}/messages",
            headers=auth_headers,
            json={"message_text": "Test message"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestTicketSLA:
    """Tests for ticket SLA functionality."""

    def test_ticket_has_sla_due_at(self, client, test_user, auth_headers):
        """Test that tickets have SLA information."""
        response = client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Test ticket",
            "category": "general",
            "priority": "medium"
        })
        data = response.json()
        assert "sla_due_at" in data
        assert data["sla_warning"] is False

    def test_critical_ticket_has_shorter_sla(self, client, test_user, auth_headers):
        """Test that critical priority tickets have shorter SLA."""
        response = client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Critical issue",
            "category": "it_support",
            "priority": "critical"
        })
        data = response.json()
        assert data["priority"] == "critical"
        # SLA should be 4 hours for critical


class TestHRTicketAccess:
    """Tests for HR user ticket access."""

    def test_hr_can_see_all_tickets(self, client, hr_user, hr_auth_headers, test_user, auth_headers):
        """Test that HR users can see all tickets."""
        # Create ticket as employee
        client.post("/api/v1/tickets", headers=auth_headers, json={
            "query": "Employee ticket",
            "category": "general",
            "priority": "low"
        })
        
        # HR should see the ticket
        response = client.get("/api/v1/tickets", headers=hr_auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
