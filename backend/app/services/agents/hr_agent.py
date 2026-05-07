"""HR specialist — ticket, leave, and HR workflow domain (delegated to main orchestrator flows)."""

from __future__ import annotations

from typing import FrozenSet

from .base import AgentContext, AgentName, AgentResult

_HR_INTENTS: FrozenSet[str] = frozenset(
    {
        "ticket_create",
        "complaint",
        "leave_request",
        "leave_balance",
        "escalate_ticket",
        "policy_query",
        "benefits_question",
    }
)


class HrAgent:
    """Signals when the primary orchestrator already owns HR flows; no duplicate automation."""

    def should_route_to_primary(self, intent: str, active_flow: str | None) -> bool:
        if active_flow in {"ticket", "leave_request"}:
            return True
        return intent in _HR_INTENTS

    def run(self, ctx: AgentContext) -> AgentResult:
        delegated = self.should_route_to_primary(ctx.intent, ctx.orchestrator.service.current_flow)
        return AgentResult(
            agent=AgentName.HR,
            handled=False,
            payload={"delegated_to_primary_flow": delegated},
        )
