"""Tests for the optional LLM nudge-eligibility gate (Phase 2)."""

import app.ai_client as ai_client_module
from app.services import mark_proactive
from app.services.mark_proactive import MarkProactiveService


def _make_service(db):
    return MarkProactiveService(db)


def test_gate_noops_when_disabled(db, test_user, monkeypatch):
    monkeypatch.setattr(mark_proactive.settings, "NUDGE_AI_GATING_ENABLED", False)
    svc = _make_service(db)
    eligible, reason = svc.decide_nudge_eligibility(
        user_id=test_user.id, nudge_type="break_reminder", message="take a break"
    )
    assert eligible is True
    assert reason == "ai_gating_disabled"


def test_gate_blocks_when_llm_says_no(db, test_user, monkeypatch):
    monkeypatch.setattr(mark_proactive.settings, "NUDGE_AI_GATING_ENABLED", True)

    class _FakeClient:
        def chat_completion(self, **_kwargs):
            return {
                "choices": [
                    {"message": {"content": '{"send": false, "reason": "user is in flow"}'}}
                ]
            }

    monkeypatch.setattr(ai_client_module, "get_ai_client", lambda *a, **k: _FakeClient())
    svc = _make_service(db)
    eligible, reason = svc.decide_nudge_eligibility(
        user_id=test_user.id, nudge_type="break_reminder", message="take a break"
    )
    assert eligible is False
    assert "flow" in reason


def test_gate_allows_when_llm_says_yes(db, test_user, monkeypatch):
    monkeypatch.setattr(mark_proactive.settings, "NUDGE_AI_GATING_ENABLED", True)

    class _FakeClient:
        def chat_completion(self, **_kwargs):
            return {
                "choices": [
                    {"message": {"content": '{"send": true, "reason": "long unbroken session"}'}}
                ]
            }

    monkeypatch.setattr(ai_client_module, "get_ai_client", lambda *a, **k: _FakeClient())
    svc = _make_service(db)
    eligible, reason = svc.decide_nudge_eligibility(
        user_id=test_user.id, nudge_type="break_reminder", message="take a break"
    )
    assert eligible is True
    assert "session" in reason


def test_gate_fails_open_on_llm_error(db, test_user, monkeypatch):
    monkeypatch.setattr(mark_proactive.settings, "NUDGE_AI_GATING_ENABLED", True)

    class _BoomClient:
        def chat_completion(self, **_kwargs):
            raise RuntimeError("upstream down")

    monkeypatch.setattr(ai_client_module, "get_ai_client", lambda *a, **k: _BoomClient())
    svc = _make_service(db)
    eligible, reason = svc.decide_nudge_eligibility(
        user_id=test_user.id, nudge_type="break_reminder", message="take a break"
    )
    assert eligible is True  # never block a nudge on an outage
    assert reason == "ai_gate_error_failopen"
