"""Productivity overlay — wraps v2 ProductivityAgent for the supplementary
dispatch pipeline. Stateless instance so the executor's shared dispatch table
can hold one copy; the inner v2 agent is rebuilt per turn from ``ctx``.
"""

from __future__ import annotations

from .base import AgentContext, AgentName, AgentResult
from ..v2.productivity_agent import ProductivityAgent as V2ProductivityAgent


class ProductivityAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        svc = ctx.orchestrator.service
        try:
            inner = V2ProductivityAgent(db=svc.db, user_id=svc.user_id)
        except Exception:
            return AgentResult(agent=AgentName.PRODUCTIVITY, handled=False, payload={"error": "init_failed"})

        out = inner.maybe_handle(ctx.message, svc.flow_context)
        if not out.handled:
            return AgentResult(agent=AgentName.PRODUCTIVITY, handled=False, payload={})
        # When the productivity agent fires it's because the user explicitly
        # asked for an email draft / meeting prep / timesheet nudge — the
        # signal is high-confidence.
        return AgentResult(
            agent=AgentName.PRODUCTIVITY,
            handled=True,
            payload={"source": "v2_productivity"},
            reply_suffix=out.reply,
            confidence=0.9,
        )
