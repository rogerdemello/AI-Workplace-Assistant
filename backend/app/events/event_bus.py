"""In-process event bus used for low-latency orchestration and analytics hooks."""

from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Callable, DefaultDict, List
import logging

from ..core.feature_flags import get_feature_flags
from .events import DomainEvent

logger = logging.getLogger(__name__)

EventHandler = Callable[[DomainEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, List[EventHandler]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        with self._lock:
            self._subscribers[event_name].append(handler)

    def publish(self, event: DomainEvent) -> None:
        if not get_feature_flags().enable_event_bus:
            return

        with self._lock:
            handlers = list(self._subscribers.get(event.name, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.warning("Event handler failed for %s: %s", event.name, exc, exc_info=True)


event_bus = EventBus()
