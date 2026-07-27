"""Coverage for the workflows completed in the friendly-hr-agent branch:
SSO (OIDC) gating, Stripe billing fallback, user invite, HRMS upsert, plus
regression tests for live-only 500s found by end-to-end probing
(analytics date-cast, burnout summary factors, buddies department, engagement
participation field, wellbeing daily check-in).
"""
from datetime import timedelta
from fastapi import status


# --- SSO (OIDC) -------------------------------------------------------------

def test_sso_providers_empty_when_unconfigured(client, monkeypatch):
    for key in ("OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_ISSUER"):
        monkeypatch.delenv(key, raising=False)
    resp = client.get("/api/v1/sso/providers")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body == {"providers": [], "enabled": False}


def test_sso_login_501_when_unconfigured(client, monkeypatch):
    for key in ("OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_ISSUER"):
        monkeypatch.delenv(key, raising=False)
    resp = client.get("/api/v1/sso/oidc/login", follow_redirects=False)
    assert resp.status_code == status.HTTP_501_NOT_IMPLEMENTED


def test_sso_providers_listed_when_configured(client, monkeypatch):
    monkeypatch.setenv("OIDC_CLIENT_ID", "client-abc")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret-xyz")
    monkeypatch.setenv("OIDC_ISSUER", "https://idp.example.com")
    monkeypatch.setenv("OIDC_PROVIDER_NAME", "Acme SSO")
    resp = client.get("/api/v1/sso/providers")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["enabled"] is True
    assert body["providers"][0]["name"] == "Acme SSO"


# --- Billing ----------------------------------------------------------------

def test_billing_config_fallback(client, hr_auth_headers, monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    monkeypatch.setenv("BILLING_PLAN_NAME", "MARK Enterprise")
    resp = client.get("/api/v1/billing/subscription", headers=hr_auth_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["source"] == "config"
    assert body["plan_name"] == "MARK Enterprise"
    # seats_used reflects the live count of active users (>= the HR user)
    assert body["seats_used"] >= 1


def test_billing_requires_hr(client, auth_headers):
    resp = client.get("/api/v1/billing/subscription", headers=auth_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# --- User invite ------------------------------------------------------------

def test_invite_user_creates_account(client, hr_auth_headers, db):
    from app.models.user import User

    resp = client.post(
        "/api/v1/users",
        headers=hr_auth_headers,
        json={"name": "Newbie", "email": "newbie@example.com", "role": "employee"},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["email"] == "newbie@example.com"
    assert body["temp_password"]
    assert body["invite_email_sent"] is False  # SMTP not configured in tests
    assert db.query(User).filter(User.email == "newbie@example.com").first() is not None


def test_invite_user_rejects_duplicate(client, hr_auth_headers, hr_user):
    resp = client.post(
        "/api/v1/users",
        headers=hr_auth_headers,
        json={"name": "Dup", "email": hr_user.email},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


def test_invite_user_forbidden_for_employee(client, auth_headers):
    resp = client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={"name": "X", "email": "x@example.com"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# --- HRMS upsert ------------------------------------------------------------

def test_hrms_sync_upserts_users(client, hr_auth_headers, db, monkeypatch):
    from app.models.user import User
    from app.services.provider_sync import ProviderSyncService

    monkeypatch.setenv("WORKDAY_BASE_URL", "https://workday.example.com")
    monkeypatch.setenv("WORKDAY_API_TOKEN", "token-123")

    def fake_request_json(self, url, token, timeout_seconds=15):
        return {
            "employees": [
                {"email": "imported@acme.com", "name": "Imported Person", "title": "Analyst", "department": "Finance"},
            ]
        }

    monkeypatch.setattr(ProviderSyncService, "_request_json", fake_request_json)

    resp = client.post(
        "/api/v1/integrations/hrms/sync",
        headers=hr_auth_headers,
        json={"provider": "workday_hrms", "dry_run": False},
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["records_changed"] >= 1
    imported = db.query(User).filter(User.email == "imported@acme.com").first()
    assert imported is not None
    assert imported.designation == "Analyst"


# --- Regression: live-only 500s caught by end-to-end probing -----------------

def _seed_user_message(db, user, label="negative"):
    """Insert one user-authored message so date-bucketing queries have rows."""
    from app.models.conversation import Conversation, Message, MessageSender, SentimentLabel
    conv = Conversation(user_id=user.id, status="active")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    db.add(Message(
        conversation_id=conv.id,
        sender=MessageSender.user,
        message_text="I am exhausted and stressed.",
        sentiment=SentimentLabel(label),
    ))
    db.commit()


def test_analytics_dashboard_ok_with_message_rows(client, hr_auth_headers, db, test_user):
    # Regression: sentiment_trend_days used cast(..., Date) which crashed SQLite
    # result processing once Message rows existed. func.date() is portable.
    _seed_user_message(db, test_user)
    resp = client.get("/api/v1/analytics/dashboard", headers=hr_auth_headers)
    assert resp.status_code == status.HTTP_200_OK
    resp2 = client.get("/api/v1/analytics/sentiment", headers=hr_auth_headers)
    assert resp2.status_code == status.HTTP_200_OK


def test_analytics_burnout_includes_factors(client, hr_auth_headers, test_user):
    # Regression: summary items dropped `factors`, failing response validation (500).
    resp = client.get("/api/v1/analytics/burnout", headers=hr_auth_headers)
    assert resp.status_code == status.HTTP_200_OK
    scores = resp.json().get("risk_scores", [])
    for item in scores:
        assert "factors" in item


def test_buddies_available_ok(client, hr_auth_headers, test_user):
    # Regression: route read User.department (nonexistent) -> AttributeError 500.
    resp = client.get("/api/v1/buddies/available", headers=hr_auth_headers)
    assert resp.status_code == status.HTTP_200_OK
    assert isinstance(resp.json(), list)


def test_wellbeing_daily_checkin_ok(client, auth_headers, test_user):
    # Regression: engagement_score referenced SurveyResponse.submitted_at (-> 500).
    resp = client.post(
        "/api/v1/wellbeing/check-ins/daily",
        headers=auth_headers,
        json={"mood": "okay", "energy_level": 5},
    )
    assert resp.status_code in (200, 201)


def test_create_conversation_persists_and_returns_id(db, test_user):
    # Regression: create_conversation now flush/commit/get (no fragile post-commit
    # refresh) so it survives concurrent access on the file-SQLite dev pool.
    from app.services.chat import ChatService
    from app.models.conversation import Conversation

    conv = ChatService(db).create_conversation(test_user.id)
    assert conv is not None and conv.id is not None
    assert db.query(Conversation).filter(Conversation.id == conv.id).first() is not None


def test_chat_conversation_start_ok(client, auth_headers):
    # The /chat page's first call — must not 500.
    resp = client.post("/api/v1/chat/conversations/start", headers=auth_headers, json={})
    assert resp.status_code in (200, 201)
    assert resp.json().get("conversation_id")


def test_sentiment_analyze_ok_with_enhanced_source(client, auth_headers):
    # Regression: SentimentResponse.source Literal omitted "enhanced", which the
    # default (USE_ENHANCED_SENTIMENT) service path returns -> response 500.
    resp = client.post(
        "/api/v1/sentiment/analyze",
        headers=auth_headers,
        json={"text": "I really love working with this team!"},
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["source"] in ("lexicon", "llm", "hybrid", "enhanced", None)
