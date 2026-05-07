"""Empathy-first overlay when tone is strained (non-clinical)."""

from __future__ import annotations

import re

from .base import AgentContext, AgentName, AgentResult

_STRESS = re.compile(
    r"\b(stress|anxious|anxiety|burnout|overwhelmed|exhausted|can't cope|depressed|sad)\b",
    re.I,
)


class EmotionalAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.intent == "emotional":
            return AgentResult(agent=AgentName.EMOTIONAL, handled=False, payload={"skip": "primary_handled"})
        text = ctx.message.lower()
        if ctx.sentiment != "negative" and not _STRESS.search(text):
            return AgentResult(agent=AgentName.EMOTIONAL, handled=False, payload={})

        prefix = "I hear you — thanks for sharing that."
        return AgentResult(
            agent=AgentName.EMOTIONAL,
            handled=True,
            payload={"tone": "supportive"},
            reply_prefix=prefix,
        )
