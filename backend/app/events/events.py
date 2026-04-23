"""Canonical event names and event envelope for backend domain signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

EVENT_MESSAGE_RECEIVED = "message_received"
EVENT_TICKET_CREATED = "ticket_created"
EVENT_SENTIMENT_DETECTED = "sentiment_detected"
EVENT_RISK_DETECTED = "risk_detected"


@dataclass(frozen=True)
class DomainEvent:
    name: str
    payload: Dict[str, Any]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
