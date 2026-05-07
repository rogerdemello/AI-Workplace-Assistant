from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any, Dict, Set


class RealtimeEventBus:
    """Best-effort in-process fanout for realtime SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {"event_type": event_type, "payload": payload}
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with suppress(asyncio.QueueFull):
                queue.put_nowait(event)


realtime_bus = RealtimeEventBus()
