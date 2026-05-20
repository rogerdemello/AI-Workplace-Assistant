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
        explicit_signal = bool(_STRESS.search(text))
        if ctx.sentiment != "negative" and not explicit_signal:
            return AgentResult(agent=AgentName.EMOTIONAL, handled=False, payload={})

        prefix = "I hear you — thanks for sharing that."
        # An explicit stress keyword is a stronger signal than a generic
        # negative-sentiment classification — score them differently so the
        # merger can suppress lukewarm overlays.
        confidence = 0.95 if explicit_signal else 0.6
        return AgentResult(
            agent=AgentName.EMOTIONAL,
            handled=True,
            payload={"tone": "supportive"},
            reply_prefix=prefix,
            confidence=confidence,
        )
