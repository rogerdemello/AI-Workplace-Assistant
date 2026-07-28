"""Security posture: route guards and PII masking.

These pin decisions that are easy to regress silently — a new route added
without a guard, or a log line that starts carrying a phone number.
"""

import pathlib
import re

import pytest
from fastapi import status

from app.middleware.security import mask_pii

API_DIR = pathlib.Path(__file__).resolve().parent.parent / "app" / "api" / "v1"

#: Routes that are unauthenticated on purpose, with the reason.
INTENTIONALLY_PUBLIC = {
    ("auth.py", "POST", "/register"),
    ("auth.py", "POST", "/login"),
    ("demo_auth.py", "POST", "/login"),
    # Inbound provider webhooks — authenticated by signature, not a session.
    ("email.py", "POST", "/inbound"),
    ("workplace.py", "GET", "/whatsapp/webhook"),
    ("workplace.py", "POST", "/whatsapp/webhook"),
    # Anonymous feedback: requiring a session would defeat the anonymity.
    ("feedback.py", "POST", "/anonymous"),
    ("feedback.py", "GET", "/anonymous/status"),  # one-time token in the query
    ("feedback.py", "GET", "/categories"),  # static list
    # SSO handshake must be reachable before a session exists.
    ("sso.py", "GET", "/providers"),
    ("sso.py", "GET", "/{provider}/login"),
    ("sso.py", "GET", "/{provider}/callback"),
    # Static reference data.
    ("webhooks.py", "GET", "/event-types"),
    ("wellness.py", "GET", "/tips"),
    ("wellness.py", "GET", "/tips/{tip_type}"),
}


def _routes_without_auth():
    found = []
    for path in sorted(API_DIR.glob("*.py")):
        src = path.read_text(encoding="utf-8", errors="replace")
        blocks = re.split(r"\n(?=@router\.(?:get|post|patch|put|delete)\()", src)
        for block in blocks[1:]:
            match = re.match(r"@router\.(get|post|patch|put|delete)\(\s*[\"']([^\"']*)", block)
            if not match:
                continue
            head = block[:1800]
            if "get_current_user" in head or "require_roles" in head:
                continue
            found.append((path.name, match.group(1).upper(), match.group(2)))
    return set(found)


def test_no_unguarded_routes_beyond_the_documented_allowlist():
    """A new route without a guard has to be a deliberate, listed decision.

    POST /tickets/sla-scan/trigger reached production unguarded: an unbounded
    database job that also reported how many tickets had breached SLA.
    """
    unexpected = _routes_without_auth() - INTENTIONALLY_PUBLIC
    assert not unexpected, (
        "unauthenticated routes not on the allowlist: "
        + ", ".join(f"{f} {v} {p}" for f, v, p in sorted(unexpected))
    )


def test_sla_scan_trigger_requires_hr(client, auth_headers):
    response = client.post("/api/v1/tickets/sla-scan/trigger", headers=auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_room_listing_requires_a_session(client):
    assert client.get("/api/v1/rooms").status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


@pytest.mark.parametrize(
    "raw",
    [
        "reach me at priya.sharma@example.com",
        "call +91 98765 43210",
        "my number is 9876543210",
        "card 4111 1111 1111 1111",
        "ssn 123-45-6789",
        "us line 555-123-4567",
    ],
)
def test_contact_details_are_masked_for_logs(raw):
    masked = mask_pii(raw)
    assert "_masked]" in masked
    # No run of 6+ digits should survive.
    assert not re.search(r"\d{6,}", masked.replace(" ", "")), masked


@pytest.mark.parametrize(
    "raw",
    [
        "uuid a5ed758b-1c15-4415-9246-175315ae5d6b",
        "processed 42 rows in 2026",
        "GET /api/v1/requests/00000000-0000-0000-0000-000000000000",
    ],
)
def test_masking_does_not_eat_ordinary_log_lines(raw):
    assert mask_pii(raw) == raw


def test_ai_mock_is_off_by_default():
    """The stub must never be reachable without an explicit opt-in.

    It answers with canned text, so a deployment that picked it up by accident
    would look healthy while giving every employee the same fabricated reply.
    """
    from app.ai_client import get_ai_client
    from app.ai_client.mock import MockAzureOpenAIClient
    from app.config import Settings

    assert Settings().AI_USE_MOCK is False
    assert not isinstance(get_ai_client(), MockAzureOpenAIClient)
