"""Detect multi-intent utterances (e.g. leave + reminder + health) for coordinated routing."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from ..health_detector import detect_health_keywords

_LEAVE = re.compile(
    r"\b("
    r"leave|pto|time\s*off|sick\s*leave|annual\s*leave|vacation|"
    r"apply\s+(for\s+)?leave|book\s+leave|request\s+leave|take\s+(the\s+)?day\s+off"
    r")\b",
    re.I,
)
_TICKET = re.compile(
    r"\b(complaint|raise\s+a\s+ticket|open\s+a\s+ticket|file\s+a\s+ticket|hr\s+ticket)\b",
    re.I,
)
_REMIND = re.compile(r"\b(remind|reminder|nudge|ping\s+me)\b", re.I)

# Capture a usable substring for proactive scheduling (passed to reminder handler).
_FRAGMENT = re.compile(
    r"\b(remind\s+me(?:\s+to|\s+about|\s+that)?\s+[^.;]+|reminder\s+(?:to|for)\s+[^.;]+)",
    re.I,
)


@dataclass
class CompoundSignals:
    wants_leave_hr: bool
    wants_ticket_hr: bool
    wants_reminder: bool
    health_signal: bool
    reminder_fragment: Optional[str]
    intent_branches: List[str]

    @property
    def branch_count(self) -> int:
        return len(self.intent_branches)

    @property
    def is_compound(self) -> bool:
        return self.branch_count >= 2

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["is_compound"] = self.is_compound
        d["branch_count"] = self.branch_count
        return d


def _extract_reminder_fragment(text: str) -> Optional[str]:
    raw = (text or "").strip()
    if not raw:
        return None
    m = _FRAGMENT.search(raw)
    if m:
        frag = m.group(0).strip().rstrip(".,;")
        return frag if len(frag) >= 8 else None
    return None


def analyze_compound(message: str) -> CompoundSignals:
    text = message or ""
    lowered = text.lower()
    health = detect_health_keywords(text)
    health_signal = bool(health.get("has_health_concern"))

    wants_leave = bool(_LEAVE.search(lowered))
    wants_ticket = bool(_TICKET.search(lowered))
    wants_reminder = bool(_REMIND.search(lowered))
    fragment = _extract_reminder_fragment(text) if wants_reminder else None

    branches: List[str] = []
    if wants_leave:
        branches.append("leave_hr")
    if wants_ticket:
        branches.append("ticket_hr")
    if wants_reminder:
        branches.append("proactive_reminder")
    if health_signal:
        branches.append("health_analysis")

    return CompoundSignals(
        wants_leave_hr=wants_leave,
        wants_ticket_hr=wants_ticket,
        wants_reminder=wants_reminder,
        health_signal=health_signal,
        reminder_fragment=fragment,
        intent_branches=branches,
    )
