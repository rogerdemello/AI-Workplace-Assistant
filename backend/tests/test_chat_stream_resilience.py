"""Chat must still answer when the language model is unreachable.

The streaming path already fell back to a buffered reply when the token stream
failed — but the buffered path calls the model too, so during a real provider
outage it failed identically. That exception escaped the SSE generator, the
response died mid-flight with "No response returned", and the employee's
message disappeared with no reply at all. For a product whose premise is that
people confide things they would not say elsewhere, silently swallowing the
turn is the worst available failure.
"""

from fastapi import status

from app.core import metrics


def _start_conversation(client, auth_headers) -> str:
    response = client.post("/api/v1/chat/conversations", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    return response.json()["id"]


def test_stream_degrades_gracefully_when_model_is_unreachable(
    client, db, test_user, auth_headers, mock_redis, monkeypatch
):
    import app.services.smart_chat as smart_chat_module

    class Unreachable(Exception):
        pass

    def boom(*_args, **_kwargs):
        raise Unreachable("Connection error.")

    # Fail both the token stream and the buffered fallback, as a provider
    # outage does.
    monkeypatch.setattr(
        smart_chat_module.SmartChatService, "stream_non_flow_intent_tokens", boom, raising=False
    )
    monkeypatch.setattr(
        smart_chat_module.SmartChatService, "_handle_general_query", boom, raising=False
    )
    monkeypatch.setattr(
        smart_chat_module.SmartChatService, "_handle_policy_query", boom, raising=False
    )

    metrics.reset()
    conversation_id = _start_conversation(client, auth_headers)

    response = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/respond/stream",
        headers=auth_headers,
        json={"message": "what is on my plate this week"},
    )

    assert response.status_code == status.HTTP_200_OK
    # The stream must complete rather than dying mid-flight.
    assert "event: done" in response.text, response.text[:500]
    assert "can't reach my language service" in response.text

    counters = metrics.snapshot()["counters"]
    assert any("chat_reply_unavailable_total" in key for key in counters), counters


def test_user_message_is_still_saved_when_the_model_is_unreachable(
    client, db, test_user, auth_headers, mock_redis, monkeypatch
):
    """The turn is saved, so nothing the employee said is lost to an outage."""
    import app.services.smart_chat as smart_chat_module
    from app.models.conversation import Conversation, Message, MessageSender

    def boom(*_args, **_kwargs):
        raise RuntimeError("Connection error.")

    monkeypatch.setattr(
        smart_chat_module.SmartChatService, "stream_non_flow_intent_tokens", boom, raising=False
    )
    monkeypatch.setattr(
        smart_chat_module.SmartChatService, "_handle_general_query", boom, raising=False
    )

    conversation_id = _start_conversation(client, auth_headers)
    text = "I have been struggling since the reorg"

    client.post(
        f"/api/v1/chat/conversations/{conversation_id}/respond/stream",
        headers=auth_headers,
        json={"message": text},
    )

    saved = (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == test_user.id, Message.sender == MessageSender.user)
        .all()
    )
    assert any(text in (m.message_text or "") for m in saved), "employee's message was lost"
