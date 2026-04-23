import uuid

from fastapi import status
from app.core.time import utcnow_naive


def test_attrition_endpoint_returns_db_backed_scores(client, db, admin_auth_headers, test_user):
    from app.models.conversation import Conversation, Message, MessageSender, SentimentLabel
    from app.models.ticket import Ticket, TicketPriority, TicketStatus

    conversation = Conversation(user_id=test_user.id)
    db.add(conversation)
    db.flush()

    db.add_all(
        [
            Message(
                conversation_id=conversation.id,
                sender=MessageSender.user,
                message_text="I feel overwhelmed lately",
                sentiment=SentimentLabel.negative,
            ),
            Message(
                conversation_id=conversation.id,
                sender=MessageSender.user,
                message_text="Work has been stressful",
                sentiment=SentimentLabel.negative,
            ),
            Message(
                conversation_id=conversation.id,
                sender=MessageSender.user,
                message_text="Need support with workload",
                sentiment=SentimentLabel.neutral,
            ),
        ]
    )

    db.add(
        Ticket(
            user_id=test_user.id,
            query="Need escalation on manager concern",
            category="manager",
            status=TicketStatus.escalated,
            priority=TicketPriority.high,
            created_at=utcnow_naive(),
        )
    )
    db.commit()

    response = client.get("/api/v1/analytics/attrition", headers=admin_auth_headers)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert isinstance(payload["risk_scores"], list)
    assert len(payload["risk_scores"]) >= 1
    assert 0 <= payload["average_risk"] <= 1

    user_risk = next((r for r in payload["risk_scores"] if r["user_id"] == str(test_user.id)), None)
    assert user_risk is not None
    assert user_risk["name"] == test_user.name
    assert user_risk["risk_level"] in {"low", "medium", "high"}
    assert 0 <= user_risk["risk_score"] <= 1


def test_attrition_endpoint_filters_by_department(client, db, admin_auth_headers):
    from app.auth import hash_password
    from app.models.department import Department
    from app.models.user import User, UserRole, UserStatus

    dept_a = Department(name="Dept A")
    dept_b = Department(name="Dept B")
    db.add_all([dept_a, dept_b])
    db.flush()

    user_a = User(
        id=uuid.uuid4(),
        email="dept-a@example.com",
        name="Dept A User",
        hashed_password=hash_password("pass123"),
        role=UserRole.employee,
        status=UserStatus.active,
        department_id=dept_a.id,
    )
    user_b = User(
        id=uuid.uuid4(),
        email="dept-b@example.com",
        name="Dept B User",
        hashed_password=hash_password("pass123"),
        role=UserRole.employee,
        status=UserStatus.active,
        department_id=dept_b.id,
    )
    db.add_all([user_a, user_b])
    db.commit()

    response = client.get(
        f"/api/v1/analytics/attrition?department_id={dept_a.id}",
        headers=admin_auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()

    assert len(payload["risk_scores"]) >= 1
    assert all(row["name"] != "Dept B User" for row in payload["risk_scores"])
    assert any(row["name"] == "Dept A User" for row in payload["risk_scores"])
