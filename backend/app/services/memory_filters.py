"""Memory filtering utilities to avoid storing low-value conversation noise."""

from __future__ import annotations

import re
from typing import Optional

NOISE_INPUTS = {
    "yes", "yeah", "yep", "ok", "okay", "sure", "thanks", "thank you",
    "no", "nope", "nah", "cool", "great", "done", "fine"
}

PREFERENCE_PATTERNS = (
    r"\\bi prefer\\b",
    r"\\bi like\\b",
    r"\\bmy preference\\b",
    r"\\busually\\b",
    r"\\balways\\b",
)

RECURRING_ACTION_PATTERNS = (
    r"\\bevery day\\b",
    r"\\bevery week\\b",
    r"\\bweekly\\b",
    r"\\bmonthly\\b",
    r"\\bremind me\\b",
)

IMPORTANT_SIGNAL_PATTERNS = (
    r"\\boverwhelmed\\b",
    r"\\bburnout\\b",
    r"\\bstress(ed)?\\b",
    r"\\bunsafe\\b",
    r"\\bharass(ed|ment)?\\b",
    r"\\bunfair\\b",
)


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def should_store_memory(
    text: str,
    *,
    intent: Optional[str] = None,
    sentiment: Optional[str] = None,
) -> bool:
    normalized = (text or "").strip().lower().strip(".!?,")
    if not normalized:
        return False

    if normalized in NOISE_INPUTS:
        return False

    if len(normalized) < 20:
        return False

    if sentiment == "negative":
        return True

    if _matches_any(normalized, PREFERENCE_PATTERNS):
        return True

    if _matches_any(normalized, RECURRING_ACTION_PATTERNS):
        return True

    if _matches_any(normalized, IMPORTANT_SIGNAL_PATTERNS):
        return True

    if intent in {"ticket_create", "leave_request", "reminder", "emotional"} and len(normalized.split()) >= 5:
        return True

    return False
