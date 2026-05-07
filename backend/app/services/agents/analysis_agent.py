"""Lightweight sentiment + health signal scoring for shared memory / merged replies."""

from __future__ import annotations

from ..health_detector import detect_health_keywords
from .base import AgentContext, AgentName, AgentResult


class AnalysisAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        health = detect_health_keywords(ctx.message)
        risk = 30
        if health.get("has_health_concern"):
            risk += min(40, len(health.get("keywords") or []) * 12)
        if ctx.sentiment == "negative":
            risk += 15

        fc = ctx.orchestrator.service.flow_context
        compound = fc.get("_mark_compound") if isinstance(fc.get("_mark_compound"), dict) else {}
        if int(compound.get("branch_count") or 0) >= 2:
            risk += 12

        fc["_mark_analysis"] = {
            "risk_score": min(100, risk),
            "health_detected": bool(health.get("has_health_concern")),
            "keywords": health.get("keywords") or [],
            "compound_branches": compound.get("intent_branches") or [],
            "compound": bool(compound.get("is_compound")),
        }

        suffix = None
        if health.get("has_health_concern") and ctx.intent not in ("emotional", "reminder"):
            # Supportive line only; not medical advice.
            suffix = (
                "If you need rest, time off, or someone from HR to check in, just say the word."
            )

        return AgentResult(
            agent=AgentName.ANALYSIS,
            handled=True,
            payload=fc["_mark_analysis"],
            reply_suffix=suffix,
        )
