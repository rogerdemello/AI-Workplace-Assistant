"""Reminder / nudge hooks layered after the primary reply when intent wasn't already reminder."""

from __future__ import annotations

import re

from .base import AgentContext, AgentName, AgentResult

_REMIND = re.compile(r"\b(remind|reminder|nudge|ping me)\b", re.I)


class ProactiveAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.intent == "reminder":
            return AgentResult(agent=AgentName.PROACTIVE, handled=False, payload={"skip": "primary_handled"})

        svc = ctx.orchestrator.service
        fc = svc.flow_context
        compound_raw = fc.get("_mark_compound")
        compound = compound_raw if isinstance(compound_raw, dict) else {}
        fragment = compound.get("reminder_fragment")

        if compound.get("wants_reminder") and isinstance(fragment, str) and len(fragment.strip()) >= 8:
            try:
                scheduled = svc._handle_reminder(fragment.strip())
                return AgentResult(
                    agent=AgentName.PROACTIVE,
                    handled=True,
                    payload={"trigger": "compound_reminder_fragment", "fragment": fragment[:200]},
                    reply_suffix=scheduled,
                )
            except Exception:
                pass

        if not _REMIND.search(ctx.message):
            return AgentResult(agent=AgentName.PROACTIVE, handled=False, payload={})

        suffix = (
            "If you'd like a formal reminder set in the system, tell me what time "
            "(or say “remind me…” again on its own and I’ll walk through it)."
        )
        return AgentResult(
            agent=AgentName.PROACTIVE,
            handled=True,
            payload={"trigger": "reminder_language"},
            reply_suffix=suffix,
        )
