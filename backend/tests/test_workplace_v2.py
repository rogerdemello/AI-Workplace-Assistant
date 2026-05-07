from fastapi import status


def test_capabilities_endpoint_returns_flags(client, auth_headers, monkeypatch):
    from app.api.v1 import workplace as workplace_api

    monkeypatch.setattr(workplace_api.settings, "ENABLE_WHATSAPP_CHANNEL", True)
    monkeypatch.setattr(workplace_api.settings, "ENABLE_LIFE_ASSISTANT", True)
    monkeypatch.setattr(workplace_api.settings, "ENABLE_PRODUCTIVITY_AGENT", False)

    response = client.get("/api/v1/workplace/capabilities", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["enable_whatsapp_channel"] is True
    assert payload["enable_life_assistant"] is True
    assert payload["enable_productivity_agent"] is False


def test_whatsapp_webhook_processes_message(client, monkeypatch):
    from app.api.v1 import workplace as workplace_api

    monkeypatch.setattr(workplace_api.settings, "ENABLE_WHATSAPP_CHANNEL", True)
    monkeypatch.setattr(workplace_api.settings, "WHATSAPP_DEFAULT_USER_EMAIL", "test@example.com")

    response = client.post(
        "/api/v1/workplace/whatsapp/webhook",
        data={
            "Body": "Hello from whatsapp",
            "From": "+911111111111",
            "To": "+12222222222",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    assert "application/xml" in response.headers.get("content-type", "")
    assert "<Response>" in response.text
    assert "<Message>" in response.text


def test_whatsapp_webhook_reuses_single_conversation(client, db, test_user, monkeypatch):
    from app.api.v1 import workplace as workplace_api
    from app.models.conversation import Conversation

    monkeypatch.setattr(workplace_api.settings, "ENABLE_WHATSAPP_CHANNEL", True)
    monkeypatch.setattr(
        workplace_api.settings,
        "WHATSAPP_USER_MAP",
        "+919999999999=test@example.com",
    )

    for body in ("first message", "second message"):
        response = client.post(
            "/api/v1/workplace/whatsapp/webhook",
            data={
                "Body": body,
                "From": "whatsapp:+919999999999",
                "To": "+10000000000",
            },
        )
        assert response.status_code == status.HTTP_200_OK

    count = db.query(Conversation).filter(Conversation.user_id == test_user.id).count()
    assert count == 1


def test_reverse_whatsapp_email_to_phone():
    from app.services.v2.capabilities import reverse_whatsapp_email_to_phone

    rev = reverse_whatsapp_email_to_phone('{"whatsapp:+911":"user@example.com"}')
    assert rev["user@example.com"] == "+911"


def test_life_assistant_handles_weather_query_when_enabled(client, auth_headers, monkeypatch):
    from app.api.v1 import workplace as workplace_api

    monkeypatch.setattr(workplace_api.settings, "ENABLE_LIFE_ASSISTANT", True)
    response = client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"message": "weather today in nagpur"},
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert "nagpur" in payload["response"].lower()
    assert "°c" in payload["response"].lower()


def test_productivity_agent_books_room_when_enabled(client, auth_headers, db, monkeypatch):
    from app.api.v1 import workplace as workplace_api
    from app.models.room import Room

    monkeypatch.setattr(workplace_api.settings, "ENABLE_PRODUCTIVITY_AGENT", True)
    room = Room(name="Orchid", capacity=8, location="L2", facilities=["screen"], is_active=True)
    db.add(room)
    db.commit()

    response = client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"message": "book a meeting room at 3 pm"},
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert "booked" in payload["response"].lower() or "free room" in payload["response"].lower()


def test_life_assistant_persists_food_preferences(client, auth_headers, db, monkeypatch, test_user):
    from app.api.v1 import workplace as workplace_api
    from app.models.user_profile import UserProfile

    monkeypatch.setattr(workplace_api.settings, "ENABLE_LIFE_ASSISTANT", True)
    response = client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"message": "where can i eat nearby veg budget"},
    )
    assert response.status_code == status.HTTP_200_OK

    profile = db.query(UserProfile).filter(UserProfile.user_id == test_user.id).first()
    assert profile is not None
    assert isinstance(profile.preferences, dict)
    food = profile.preferences.get("food_preferences", {})
    assert food.get("diet") == "veg"
    assert food.get("budget") == "budget"


def test_productivity_agent_confirms_slot_and_schedules_with_calendar(client, auth_headers, db, monkeypatch, test_user):
    from app.api.v1 import workplace as workplace_api
    from app.services.v2 import productivity_agent as productivity_module

    monkeypatch.setattr(workplace_api.settings, "ENABLE_PRODUCTIVITY_AGENT", True)
    monkeypatch.setattr(
        productivity_module.ProductivityAgent,
        "_suggest_meeting_slots",
        lambda self: ["2030-01-01 10:00-11:00"],
    )
    monkeypatch.setattr(
        productivity_module.ProductivityAgent,
        "_create_calendar_event_for_slot",
        lambda self, slot_label, attendees: True,
    )

    first = client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"message": "schedule a meeting with rahul"},
    )
    assert first.status_code == status.HTTP_200_OK
    first_payload = first.json()
    assert "found these slots" in first_payload["response"].lower()
    conversation_id = first_payload["conversation_id"]

    confirm = client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"message": "book first slot", "conversation_id": conversation_id},
    )
    assert confirm.status_code == status.HTTP_200_OK
    assert "meeting scheduled" in confirm.json()["response"].lower()
