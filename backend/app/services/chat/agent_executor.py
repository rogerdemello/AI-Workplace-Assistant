"""Runs supplementary agents and collects structured results."""

from __future__ import annotations

from typing import Any, List, Tuple

from ..agents.analysis_agent import AnalysisAgent
from ..agents.base import AgentContext, AgentName, AgentResult
from ..agents.emotional_agent import EmotionalAgent
from ..agents.proactive_agent import ProactiveAgent
from .contracts import AgentExecutionEnvelope

_DISPATCH = {
    AgentName.ANALYSIS: AnalysisAgent(),
    AgentName.EMOTIONAL: EmotionalAgent(),
    AgentName.PROACTIVE: ProactiveAgent(),
}


def execute_supplementary_agents(
    plan_supplementary: Tuple[AgentName, ...],
    ctx: AgentContext,
) -> tuple[List[AgentResult], AgentExecutionEnvelope]:
    results: List[AgentResult] = []
    successful_agents: list[str] = []
    failed_agents: list[str] = []
    requested_agents = [name.value for name in plan_supplementary]

    for name in plan_supplementary:
        runner = _DISPATCH.get(name)
        if runner is None:
            failed_agents.append(name.value)
            continue
        try:
            result = runner.run(ctx)
            results.append(result)
            successful_agents.append(name.value)
        except Exception:
            failed_agents.append(name.value)
            results.append(
                AgentResult(agent=name, handled=False, payload={"error": "agent_failed"})
            )
    envelope = AgentExecutionEnvelope(
        requested_agents=requested_agents,
        successful_agents=successful_agents,
        failed_agents=failed_agents,
        has_failures=bool(failed_agents),
    )
    return results, envelope
