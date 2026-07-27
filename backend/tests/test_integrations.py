from datetime import timedelta

from fastapi import status
from app.core.time import utcnow_naive


def test_google_auth_stores_oauth_state(client, auth_headers, test_user, db):
    from app.models.calendar_integration import CalendarIntegration

    response = client.get(
        "/api/v1/integrations/calendar/google/auth",
        headers=auth_headers,
        params={"redirect_uri": "http://localhost:3000/callback"},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["provider"] == "google"
    assert payload["state"]
    assert "auth_url" in payload

    row = db.query(CalendarIntegration).filter(
        CalendarIntegration.user_id == test_user.id,
        CalendarIntegration.provider == "google",
    ).first()

    assert row is not None
    assert row.oauth_state_hash is not None
    assert row.oauth_state_expires_at is not None


def test_oauth_callback_stores_tokens_and_status(client, auth_headers, monkeypatch):
    from app.services.calendar import CalendarService

    async def fake_exchange_google_code(code: str, redirect_uri: str):
        assert code == "fake-auth-code"
        assert redirect_uri == "http://localhost:3000/callback"
        return {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "expires_in": 3600,
        }

    monkeypatch.setattr(CalendarService, "exchange_google_code", staticmethod(fake_exchange_google_code))

    auth_resp = client.get(
        "/api/v1/integrations/calendar/google/auth",
        headers=auth_headers,
        params={"redirect_uri": "http://localhost:3000/callback"},
    )
    state_token = auth_resp.json()["state"]

    callback_resp = client.post(
        "/api/v1/integrations/calendar/google/callback",
        headers=auth_headers,
        json={
            "code": "fake-auth-code",
            "state": state_token,
            "redirect_uri": "http://localhost:3000/callback",
        },
    )

    assert callback_resp.status_code == status.HTTP_200_OK
    callback_payload = callback_resp.json()
    assert callback_payload["status"] == "connected"
    assert callback_payload["provider"] == "google"

    status_resp = client.get(
        "/api/v1/integrations/calendar/google/status",
        headers=auth_headers,
    )
    assert status_resp.status_code == status.HTTP_200_OK
    status_payload = status_resp.json()
    assert status_payload["connected"] is True
    assert status_payload["has_refresh_token"] is True
    assert status_payload["expires_at"] is not None


def test_availability_requires_calendar_connection(client, auth_headers):
    start = utcnow_naive()
    end = start + timedelta(days=1)

    response = client.get(
        "/api/v1/integrations/calendar/availability",
        headers=auth_headers,
        params={
            "provider": "google",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "not connected" in response.json()["detail"].lower()


def test_create_event_requires_calendar_connection(client, auth_headers):
    start = utcnow_naive() + timedelta(days=1)
    end = start + timedelta(hours=1)

    response = client.post(
        "/api/v1/integrations/calendar/events",
        headers=auth_headers,
        params={"provider": "microsoft"},
        json={
            "title": "Skip Level",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "attendees": ["hr@example.com"],
            "timezone": "UTC",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "not connected" in response.json()["detail"].lower()


def test_list_calendar_events_for_connected_provider(client, auth_headers, db, test_user, monkeypatch):
    from app.models.calendar_integration import CalendarIntegration
    from app.services.calendar import CalendarService

    integration = CalendarIntegration(
        user_id=test_user.id,
        provider="google",
        access_token="valid-access",
        refresh_token="valid-refresh",
        connected_at=utcnow_naive(),
    )
    db.add(integration)
    db.commit()

    async def fake_list_events(self, start_date, end_date, max_results):
        return [
            {
                "id": "evt_1",
                "title": "1:1",
                "start_time": start_date.isoformat(),
                "end_time": end_date.isoformat(),
                "attendees": ["hr@example.com"],
                "status": "confirmed",
                "provider": "google",
                "web_link": "https://calendar.google.com/event?eid=evt_1",
            }
        ]

    monkeypatch.setattr(CalendarService, "list_events", fake_list_events)

    response = client.get(
        "/api/v1/integrations/calendar/events",
        headers=auth_headers,
        params={"provider": "google"},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["provider"] == "google"
    assert payload["count"] == 1
    assert payload["events"][0]["id"] == "evt_1"


def test_delete_calendar_event_returns_404_when_missing(client, auth_headers, db, test_user, monkeypatch):
    from app.models.calendar_integration import CalendarIntegration
    from app.services.calendar import CalendarService

    integration = CalendarIntegration(
        user_id=test_user.id,
        provider="microsoft",
        access_token="valid-access",
        refresh_token="valid-refresh",
        connected_at=utcnow_naive(),
    )
    db.add(integration)
    db.commit()

    async def fake_delete_event(self, event_id):
        return False

    monkeypatch.setattr(CalendarService, "delete_event", fake_delete_event)

    response = client.delete(
        "/api/v1/integrations/calendar/events/nonexistent-id",
        headers=auth_headers,
        params={"provider": "microsoft"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_list_integration_providers_includes_stub_connectors(client, auth_headers):
    response = client.get("/api/v1/integrations/providers", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    rows = response.json()
    keys = {row["key"] for row in rows}
    assert "google_calendar" in keys
    assert "microsoft_calendar" in keys
    assert "workday_hrms" in keys
    assert "adp_payroll" in keys


def test_hrms_sync_stub_runs_with_supported_provider(client, auth_headers):
    response = client.post(
        "/api/v1/integrations/hrms/sync",
        headers=auth_headers,
        json={"provider": "workday_hrms", "dry_run": True},
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["category"] == "hrms"
    assert payload["dry_run"] is True
    assert payload["records_seen"] >= 1


def test_payroll_sync_stub_rejects_unknown_provider(client, auth_headers):
    response = client.post(
        "/api/v1/integrations/payroll/sync",
        headers=auth_headers,
        json={"provider": "unknown_payroll", "dry_run": True},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "unsupported payroll provider" in response.json()["detail"].lower()


def test_hrms_sync_uses_live_path_when_provider_credentials_present(client, auth_headers, monkeypatch):
    from app.api.v1 import integrations as integrations_api

    monkeypatch.setenv("WORKDAY_BASE_URL", "https://workday.example.com")
    monkeypatch.setenv("WORKDAY_API_TOKEN", "token-123")

    def fake_live_sync(provider: str, category: str, dry_run: bool, db=None):
        assert provider == "workday_hrms"
        assert category == "hrms"
        assert dry_run is False
        return integrations_api.IntegrationSyncResponse(
            provider=provider,
            category=category,
            status="ok",
            dry_run=False,
            records_seen=15,
            records_changed=8,
            details="Live HRMS sync executed.",
        )

    monkeypatch.setattr(integrations_api, "_run_live_sync", fake_live_sync)

    response = client.post(
        "/api/v1/integrations/hrms/sync",
        headers=auth_headers,
        json={"provider": "workday_hrms", "dry_run": False},
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["category"] == "hrms"
    assert payload["records_seen"] == 15
    assert payload["records_changed"] == 8


def test_payroll_sync_uses_live_path_when_provider_credentials_present(client, auth_headers, monkeypatch):
    from app.api.v1 import integrations as integrations_api

    monkeypatch.setenv("ADP_BASE_URL", "https://adp.example.com")
    monkeypatch.setenv("ADP_API_TOKEN", "token-123")

    def fake_live_sync(provider: str, category: str, dry_run: bool, db=None):
        assert provider == "adp_payroll"
        assert category == "payroll"
        assert dry_run is False
        return integrations_api.IntegrationSyncResponse(
            provider=provider,
            category=category,
            status="ok",
            dry_run=False,
            records_seen=9,
            records_changed=5,
            details="Live payroll sync executed.",
        )

    monkeypatch.setattr(integrations_api, "_run_live_sync", fake_live_sync)

    response = client.post(
        "/api/v1/integrations/payroll/sync",
        headers=auth_headers,
        json={"provider": "adp_payroll", "dry_run": False},
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["category"] == "payroll"
    assert payload["records_seen"] == 9
    assert payload["records_changed"] == 5
