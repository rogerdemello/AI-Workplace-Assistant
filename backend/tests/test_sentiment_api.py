from fastapi import status


def test_sentiment_trend_uses_message_history(client, db, auth_headers, test_user):
    from app.models.conversation import Conversation, Message, MessageSender, SentimentLabel

    convo = Conversation(user_id=test_user.id)
    db.add(convo)
    db.flush()

    db.add_all(
        [
            Message(
                conversation_id=convo.id,
                sender=MessageSender.user,
                message_text="This is amazing",
                sentiment=SentimentLabel.positive,
            ),
            Message(
                conversation_id=convo.id,
                sender=MessageSender.user,
                message_text="I am frustrated",
                sentiment=SentimentLabel.negative,
            ),
            Message(
                conversation_id=convo.id,
                sender=MessageSender.user,
                message_text="Okay thanks",
                sentiment=SentimentLabel.neutral,
            ),
        ]
    )
    db.commit()

    response = client.get("/api/v1/sentiment/trend?days=7", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_analyses"] == 3
    assert data["positive_percentage"] > 0
    assert data["negative_percentage"] > 0
    assert data["neutral_percentage"] > 0
    assert data["trend"] in {"improving", "stable", "declining"}


def test_sentiment_trend_with_no_messages_returns_neutral_baseline(client, auth_headers):
    response = client.get("/api/v1/sentiment/trend?days=7", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_analyses"] == 0
    assert data["average_sentiment"] == 0.0
    assert data["neutral_percentage"] == 100.0


def test_emotion_tag_detects_stress_signal(client, auth_headers):
    response = client.post(
        "/api/v1/sentiment/emotion-tag",
        headers=auth_headers,
        json={"text": "I feel overwhelmed and exhausted today"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["emotion"] in {"stress", "frustration"}
    assert data["sentiment"] in {"negative", "neutral"}
    assert 0.0 <= data["confidence"] <= 1.0
    assert "secondary_emotions" in data
