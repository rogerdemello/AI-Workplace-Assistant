"""Sentiment trend rows from Supabase messages."""

from __future__ import annotations

from typing import Any, List, Optional


def sentiment_trend_rows(messages: Optional[List[dict[str, Any]]]) -> list[dict[str, Any]]:
    if not messages:
        return []
    out: list[dict[str, Any]] = []
    for m in messages:
        sent = (m.get("sentiment") or "").lower()
        score = 1 if sent == "positive" else 0 if sent == "negative" else 0.5
        out.append({"date": m.get("created_at"), "score": score})
    return out
