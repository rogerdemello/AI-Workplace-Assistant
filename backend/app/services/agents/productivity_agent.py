"""Productivity — wraps v2 ProductivityAgent for optional direct execution."""

from __future__ import annotations

from .base import AgentContext, AgentName, AgentResult
from ..v2.productivity_agent import ProductivityAgent as V2ProductivityAgent


class ProductivityAgent:
    def __init__(self, ctx: AgentContext) -> None:
        svc = ctx.orchestrator.service
        self._inner = V2ProductivityAgent(db=svc.db, user_id=svc.user_id)

    def run(self, ctx: AgentContext) -> AgentResult:
        fc = ctx.orchestrator.service.flow_context
        out = self._inner.maybe_handle(ctx.message, fc)
        if not out.handled:
            return AgentResult(agent=AgentName.PRODUCTIVITY, handled=False, payload={})
        return AgentResult(
            agent=AgentName.PRODUCTIVITY,
            handled=True,
            payload={"source": "v2_productivity"},
            reply_suffix=out.reply,
        )
