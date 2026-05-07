"""Chat → sentiment pipeline → HR-visible logs (sentiment_logs / employee scores)."""

from fastapi import status

from app.models.sentiment_log import SentimentLog


def test_unified_chat_message_persists_sentiment_for_employee(client, db, test_user, auth_headers, mock_redis):
    before = db.query(SentimentLog).filter(SentimentLog.employee_id == test_user.id).count()
    response = client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"message": "I am really stressed and burned out this week"},
    )
    assert response.status_code == status.HTTP_200_OK
    after = db.query(SentimentLog).filter(SentimentLog.employee_id == test_user.id).count()
    assert after > before


def test_respond_to_message_persists_sentiment_for_employee(client, db, test_user, auth_headers, mock_redis):
    conv_response = client.post("/api/v1/chat/conversations", headers=auth_headers)
    assert conv_response.status_code == status.HTTP_200_OK
    conversation_id = conv_response.json()["id"]

    before = db.query(SentimentLog).filter(SentimentLog.employee_id == test_user.id).count()
    response = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/respond",
        headers=auth_headers,
        json={"message": "I feel overwhelmed and frustrated with my workload"},
    )
    assert response.status_code == status.HTTP_200_OK
    after = db.query(SentimentLog).filter(SentimentLog.employee_id == test_user.id).count()
    assert after > before


def test_add_message_endpoint_persists_sentiment_for_employee(client, db, test_user, auth_headers, mock_redis):
    conv_response = client.post("/api/v1/chat/conversations", headers=auth_headers)
    assert conv_response.status_code == status.HTTP_200_OK
    conversation_id = conv_response.json()["id"]

    before = db.query(SentimentLog).filter(SentimentLog.employee_id == test_user.id).count()
    response = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/messages",
        headers=auth_headers,
        json={
            "message_text": "My workload is too much and I feel anxious",
            "sender": "user",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    after = db.query(SentimentLog).filter(SentimentLog.employee_id == test_user.id).count()
    assert after > before


def test_stream_respond_persists_sentiment_for_employee(client, db, test_user, auth_headers, mock_redis):
    conv_response = client.post("/api/v1/chat/conversations", headers=auth_headers)
    assert conv_response.status_code == status.HTTP_200_OK
    conversation_id = conv_response.json()["id"]

    before = db.query(SentimentLog).filter(SentimentLog.employee_id == test_user.id).count()
    response = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/respond/stream",
        headers=auth_headers,
        json={"message": "I am stressed and frustrated at work"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "event: done" in response.text
    after = db.query(SentimentLog).filter(SentimentLog.employee_id == test_user.id).count()
    assert after > before
