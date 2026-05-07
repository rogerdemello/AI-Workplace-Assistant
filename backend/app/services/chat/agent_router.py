"""Route one turn to specialist agents with a structured orchestrator decision."""

from __future__ import annotations

import re
from typing import Any, Dict

from ..agents.base import AgentName
from .contracts import AgentRoutingDecision, MultiAgentPlanContract

_REMIND_LANG = re.compile(r"\b(remind|reminder|nudge|ping me)\b", re.I)
_NEG_TONE = re.compile(
    r"\b(stress|anxious|anxiety|burnout|overwhelmed|exhausted|can't cope|depressed|sad)\b",
    re.I,
)


def _compound_view(orchestrator: Any) -> Dict[str, Any]:
    raw = orchestrator.service.flow_context.get("_mark_compound")
    return raw if isinstance(raw, dict) else {}


class AgentRouter:
    def plan(
        self,
        *,
        message: str,
        intent: str,
        sentiment: str,
        orchestrator: Any,
    ) -> MultiAgentPlanContract:
        supplementary: list[AgentName] = [AgentName.ANALYSIS]
        ml = (message or "").strip()
        c = _compound_view(orchestrator)

        emotional = (
            sentiment == "negative"
            or bool(_NEG_TONE.search(ml))
            or (
                bool(c.get("health_signal"))
                and (bool(c.get("is_compound")) or bool(c.get("wants_leave_hr")))
            )
        )
        if emotional:
            supplementary.append(AgentName.EMOTIONAL)

        proactive_ok = intent != "reminder" and (
            bool(_REMIND_LANG.search(ml))
            or bool(c.get("wants_reminder"))
        )
        if proactive_ok:
            supplementary.append(AgentName.PROACTIVE)

        entities = self._extract_entities(message=ml, compound=c)
        agents = [a.value for a in supplementary]
        decision = AgentRoutingDecision(
            intent=intent or "general_query",
            agents=agents,
            entities=entities,
            priority=self._priority_for(intent=intent, sentiment=sentiment, compound=c),
            multi_agent=len(agents) > 1,
        )
        return MultiAgentPlanContract(supplementary=tuple(supplementary), decision=decision)

    @staticmethod
    def _extract_entities(message: str, compound: Dict[str, Any]) -> Dict[str, Any]:
        entities: Dict[str, Any] = {}
        if compound.get("wants_leave_hr"):
            entities["leave_request"] = True
        if compound.get("wants_ticket_hr"):
            entities["ticket_request"] = True
        if compound.get("wants_reminder"):
            entities["reminder_request"] = True
        fragment = compound.get("reminder_fragment")
        if fragment:
            entities["reminder_text"] = str(fragment)

        date_hint = re.search(r"\b(today|tomorrow)\b", message, re.I)
        if date_hint:
            entities["date_hint"] = date_hint.group(1).lower()
        time_hint = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", message, re.I)
        if time_hint:
            entities["time_hint"] = time_hint.group(1).strip().lower()
        return entities

    @staticmethod
    def _priority_for(intent: str, sentiment: str, compound: Dict[str, Any]) -> str:
        if sentiment == "negative" or compound.get("health_signal"):
            return "high"
        if compound.get("is_compound") or intent in {"leave_request", "ticket_create", "complaint"}:
            return "medium"
        return "low"
