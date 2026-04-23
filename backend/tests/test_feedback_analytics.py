from fastapi import status


def test_submit_chat_csat_requires_auth(client):
    response = client.post(
        "/api/v1/feedback/csat",
        json={"rating": 4},
    )
    assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


def test_submit_chat_csat_updates_weekly_quality(client, auth_headers, hr_auth_headers, mock_redis):
    conv_response = client.post("/api/v1/chat/conversations", headers=auth_headers)
    assert conv_response.status_code == status.HTTP_200_OK
    conversation_id = conv_response.json()["id"]

    csat_response = client.post(
        "/api/v1/feedback/csat",
        headers=auth_headers,
        json={
            "rating": 5,
            "conversation_id": conversation_id,
            "intent": "general_query",
            "sentiment": "positive",
        },
    )
    assert csat_response.status_code == status.HTTP_201_CREATED
    csat_data = csat_response.json()
    assert csat_data["rating"] == 5
    assert csat_data["status"] == "submitted"

    dashboard_response = client.get("/api/v1/analytics/dashboard", headers=hr_auth_headers)
    assert dashboard_response.status_code == status.HTTP_200_OK

    weekly_quality = dashboard_response.json()["weekly_quality"]
    assert weekly_quality["feedback_responses"] >= 1
    assert weekly_quality["avg_csat"] >= 5.0
    assert "quality_label" in weekly_quality


def test_memory_cards_from_chat_history(client, auth_headers, mock_redis):
    conv_response = client.post("/api/v1/chat/conversations", headers=auth_headers)
    assert conv_response.status_code == status.HTTP_200_OK
    conversation_id = conv_response.json()["id"]

    message_response = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/messages",
        headers=auth_headers,
        json={"message_text": "I need help planning paid leave for next month", "sender": "user"},
    )
    assert message_response.status_code == status.HTTP_200_OK

    cards_response = client.get("/api/v1/chat/memory-cards?limit=3", headers=auth_headers)
    assert cards_response.status_code == status.HTTP_200_OK

    cards = cards_response.json()
    assert isinstance(cards, list)
    assert len(cards) >= 1
    assert "summary" in cards[0]
