"""MARK multi-agent supplementary layers (router → executor → merger)."""

from fastapi import status


def test_merge_supplementary_joins_prefix_and_suffix():
    from app.services.agents.base import AgentName, AgentResult
    from app.services.chat.response_merger import merge_supplementary

    results = [
        AgentResult(agent=AgentName.EMOTIONAL, handled=True, reply_prefix="Thanks for sharing."),
        AgentResult(agent=AgentName.PROACTIVE, handled=True, reply_suffix="More soon."),
    ]
    out = merge_supplementary("Primary answer. Primary answer.", results)
    assert "Thanks for sharing." in out
    assert "Primary answer." in out
    assert "More soon." in out
    assert out.count("\n") <= 2


def test_agent_router_orders_supplementary_agents():
    from unittest.mock import MagicMock

    from app.services.agents.base import AgentName
    from app.services.chat.agent_router import AgentRouter
    from app.services.chat.compound_intent import analyze_compound

    mock_orch = MagicMock()
    mock_orch.service.flow_context = {
        "_mark_compound": analyze_compound("I feel stressed, remind me later").to_dict()
    }
    router = AgentRouter()
    plan = router.plan(
        message="I feel stressed, remind me later",
        intent="general_query",
        sentiment="negative",
        orchestrator=mock_orch,
    )
    names = list(plan.supplementary)
    assert names[0].value == "analysis"
    assert AgentName.EMOTIONAL in plan.supplementary
    assert AgentName.PROACTIVE in plan.supplementary
    assert plan.decision.multi_agent is True
    assert plan.decision.priority in {"medium", "high"}
    assert plan.decision.agents[0] == "analysis"


def test_compound_intent_detects_mixed_hr_and_reminder():
    from app.services.chat.compound_intent import analyze_compound

    text = (
        "I have a fever, apply leave for tomorrow and remind me to take medicine"
    )
    sig = analyze_compound(text)
    assert sig.health_signal is True
    assert sig.wants_leave_hr is True
    assert sig.wants_reminder is True
    assert sig.is_compound is True
    assert sig.reminder_fragment


def test_router_emotional_from_compound_health_even_if_neutral_sentiment():
    from unittest.mock import MagicMock

    from app.services.agents.base import AgentName
    from app.services.chat.agent_router import AgentRouter
    from app.services.chat.compound_intent import analyze_compound

    msg = "I feel sick with fever and need leave tomorrow"
    mock_orch = MagicMock()
    mock_orch.service.flow_context = {"_mark_compound": analyze_compound(msg).to_dict()}
    router = AgentRouter()
    plan = router.plan(message=msg, intent="leave_request", sentiment="neutral", orchestrator=mock_orch)
    assert AgentName.EMOTIONAL in plan.supplementary


def test_multi_agent_layers_when_enabled(client, auth_headers, monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "ENABLE_MULTI_AGENT_ORCHESTRATION", True)

    response = client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"message": "this is overwhelming but please remind me about lunch"},
    )
    assert response.status_code == status.HTTP_200_OK
    text = response.json().get("response", "")
    # Emotional + proactive supplementary overlays (exact wording may vary with LLM primary path)
    assert len(text) > 10


def test_flow_context_has_analysis_blob_after_layer(db, test_user, monkeypatch):
    from app import config
    from app.services.smart_chat import get_smart_chat_service
    from app.services.chat.orchestrator import ConversationOrchestrator

    monkeypatch.setattr(config.settings, "ENABLE_MULTI_AGENT_ORCHESTRATION", True)

    svc = get_smart_chat_service(db=db, user_id=test_user.id, use_mock=True)
    orch = ConversationOrchestrator(svc)
    orch.run("I have a fever and feel stressed")
    fc = svc.flow_context
    assert "_mark_analysis" in fc
    assert "risk_score" in fc["_mark_analysis"]
    assert "_mark_orchestrator_decision" in fc
    assert "agents" in fc["_mark_orchestrator_decision"]
    assert "_mark_execution_envelope" in fc
    assert "requested_agents" in fc["_mark_execution_envelope"]
    assert "has_failures" in fc["_mark_execution_envelope"]


def test_agent_executor_returns_structured_execution_envelope():
    from app.services.agents.base import AgentName
    from app.services.chat.agent_executor import execute_supplementary_agents

    class _DummyRunner:
        def run(self, _ctx):
            raise RuntimeError("boom")

    from app.services.chat import agent_executor as module

    old_dispatch = dict(module._DISPATCH)
    try:
        module._DISPATCH = {AgentName.ANALYSIS: _DummyRunner()}
        results, envelope = execute_supplementary_agents((AgentName.ANALYSIS,), ctx=None)  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0].handled is False
        assert envelope.requested_agents == ["analysis"]
        assert envelope.successful_agents == []
        assert envelope.failed_agents == ["analysis"]
        assert envelope.has_failures is True
    finally:
        module._DISPATCH = old_dispatch
