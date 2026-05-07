from fastapi import status


def test_email_draft_triggers_webhook_event(client, auth_headers, monkeypatch):
    from app.api.v1 import email as email_api

    captured = {}

    def fake_generate_draft(self, email_type: str, tone: str, context=None):
        return {
            "subject": "Draft subject",
            "body": "Draft body",
            "tone": tone,
            "type": email_type,
            "context": context or {},
        }

    def fake_trigger_webhooks(db, event_type: str, payload: dict):
        captured["event_type"] = event_type
        captured["payload"] = payload
        return []

    monkeypatch.setattr(email_api.EmailDraftService, "generate_draft", fake_generate_draft)
    monkeypatch.setattr(email_api.webhook_service, "trigger_webhooks", fake_trigger_webhooks)

    response = client.post(
        "/api/v1/email/draft",
        headers=auth_headers,
        json={
            "type": "general",
            "tone": "friendly",
            "context": {"recipient_name": "Team"},
        },
    )
    assert response.status_code == status.HTTP_200_OK
    assert captured.get("event_type") == "email_draft_created"
    assert captured.get("payload", {}).get("email_type") == "general"


def test_email_send_triggers_webhook_event(client, auth_headers, monkeypatch):
    from app.api.v1 import email as email_api

    captured = {}

    def fake_send_email_via_smtp(*, to: str, subject: str, body: str, cc=None):
        assert to == "team@example.com"
        assert subject == "Weekly update"
        assert body
        return None

    def fake_trigger_webhooks(db, event_type: str, payload: dict):
        captured["event_type"] = event_type
        captured["payload"] = payload
        return []

    monkeypatch.setattr(email_api, "send_email_via_smtp", fake_send_email_via_smtp)
    monkeypatch.setattr(email_api.webhook_service, "trigger_webhooks", fake_trigger_webhooks)

    response = client.post(
        "/api/v1/email/send",
        headers=auth_headers,
        json={
            "to": "team@example.com",
            "subject": "Weekly update",
            "body": "Hello team",
            "cc": ["hr@example.com"],
        },
    )
    assert response.status_code == status.HTTP_200_OK
    assert captured.get("event_type") == "email_sent"
    assert captured.get("payload", {}).get("to") == "team@example.com"
    assert captured.get("payload", {}).get("cc_count") == 1


def test_inbound_email_creates_ticket_and_triggers_webhook(client, test_user, monkeypatch):
    from app.api.v1 import email as email_api

    captured = {}

    def fake_trigger_webhooks(db, event_type: str, payload: dict):
        captured["event_type"] = event_type
        captured["payload"] = payload
        return []

    monkeypatch.setattr(email_api.webhook_service, "trigger_webhooks", fake_trigger_webhooks)

    # Ensure there is a deterministic secret and pass it in header.
    monkeypatch.setenv("EMAIL_HOOK_SECRET", "hook-secret-123")

    response = client.post(
        "/api/v1/email/inbound",
        headers={"x-email-hook-secret": "hook-secret-123"},
        json={
            "provider": "gmail",
            "from_email": "employee@external.com",
            "to_email": "test@example.com",
            "subject": "Need help with manager discussion",
            "body": "Please route this concern to HR support.",
            "message_id": "msg-123",
        },
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    payload = response.json()
    assert payload.get("status") == "accepted"
    assert payload.get("ticket_id")
    assert captured.get("event_type") == "email_received"
    assert captured.get("payload", {}).get("provider") == "gmail"
