"""Dashboard aggregates from Supabase-shaped rows."""

from __future__ import annotations

from typing import Any, List, Optional


def engagement_percent_from_messages(messages: Optional[List[dict[str, Any]]]) -> int:
    if not messages:
        return 50
    positive = sum(1 for m in messages if (m.get("sentiment") or "").lower() == "positive")
    total = len(messages)
    return int((positive / total) * 100) if total else 50


def risk_level_from_engagement(engagement_score: int) -> str:
    if engagement_score < 50:
        return "High"
    if engagement_score < 70:
        return "Medium"
    return "Low"


def count_open_tickets(
    tickets: Optional[List[dict[str, Any]]],
    open_statuses: frozenset[str] | None = None,
) -> int:
    if not tickets:
        return 0
    open_statuses = open_statuses or frozenset(
        {"open", "in_progress", "escalated", "pending"}
    )
    lowered = {s.lower() for s in open_statuses}
    return sum(
        1
        for t in tickets
        if (t.get("status") or "open").lower() in lowered
    )
