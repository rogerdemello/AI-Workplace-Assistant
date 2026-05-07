"""Life / daily assistant — wraps v2 LifeAssistantAgent for optional direct execution."""

from __future__ import annotations

from .base import AgentContext, AgentName, AgentResult
from ..v2.life_assistant_agent import LifeAssistantAgent


class LifeAgent:
    def __init__(self, ctx: AgentContext) -> None:
        svc = ctx.orchestrator.service
        self._inner = LifeAssistantAgent(db=svc.db, user_id=svc.user_id)

    def run(self, ctx: AgentContext) -> AgentResult:
        out = self._inner.maybe_handle(ctx.message)
        if not out.handled:
            return AgentResult(agent=AgentName.LIFE, handled=False, payload={})
        return AgentResult(
            agent=AgentName.LIFE,
            handled=True,
            payload={"source": "v2_life_assistant"},
            reply_suffix=out.reply,
        )
