"""Latency helpers for chat: fast sentiment tagging without blocking on hybrid LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import settings

if TYPE_CHECKING:
    from .sentiment import SentimentService


def sync_chat_sentiment_label_score(sentiment_service: "SentimentService", text: str) -> tuple[str, float]:
    """
    Tag the user turn for persistence / HR pipeline.
    When CHAT_SYNC_LEXICON_SENTIMENT (default True) or FAST_CHAT_MODE: lexicon only (no extra LLM).
    Set CHAT_SYNC_LEXICON_SENTIMENT=false to run full hybrid analyze() on every chat message (slower).
    """
    if settings.FAST_CHAT_MODE or settings.CHAT_SYNC_LEXICON_SENTIMENT:
        r = sentiment_service.analyze_lexicon_only(text)
    else:
        r = sentiment_service.analyze(text)
    return str(r.get("sentiment", "neutral")), float(r.get("score", 0.0))
