"""Dashboard aggregates from Supabase-shaped rows."""

from __future__ import annotations

from threading import Lock
from typing import Any, Dict, List, Optional

from ..events import event_bus
from ..events.events import (
    DomainEvent,
    EVENT_MESSAGE_RECEIVED,
    EVENT_TICKET_CREATED,
    EVENT_SENTIMENT_DETECTED,
)


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


class RealtimeAnalyticsTracker:
    """In-memory analytics accumulator fed by domain events."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.message_count = 0
        self.ticket_count = 0
        self.sentiment_counts: Dict[str, int] = {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
        }

    def on_message_received(self, _event: DomainEvent) -> None:
        with self._lock:
            self.message_count += 1

    def on_ticket_created(self, _event: DomainEvent) -> None:
        with self._lock:
            self.ticket_count += 1

    def on_sentiment_detected(self, event: DomainEvent) -> None:
        label = str(event.payload.get("sentiment") or "neutral").lower()
        if label not in self.sentiment_counts:
            label = "neutral"
        with self._lock:
            self.sentiment_counts[label] += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            total = sum(self.sentiment_counts.values())
            positive = self.sentiment_counts["positive"]
            engagement_score = int((positive / total) * 100) if total else 50
            return {
                "messages_seen": self.message_count,
                "tickets_seen": self.ticket_count,
                "sentiment_counts": dict(self.sentiment_counts),
                "engagement_score": engagement_score,
            }


_tracker = RealtimeAnalyticsTracker()
_subscriptions_registered = False


def register_event_driven_analytics() -> None:
    """Attach analytics listeners to the process-local event bus once."""
    global _subscriptions_registered
    if _subscriptions_registered:
        return

    event_bus.subscribe(EVENT_MESSAGE_RECEIVED, _tracker.on_message_received)
    event_bus.subscribe(EVENT_TICKET_CREATED, _tracker.on_ticket_created)
    event_bus.subscribe(EVENT_SENTIMENT_DETECTED, _tracker.on_sentiment_detected)
    _subscriptions_registered = True


def get_realtime_analytics_snapshot() -> Dict[str, Any]:
    return _tracker.snapshot()
