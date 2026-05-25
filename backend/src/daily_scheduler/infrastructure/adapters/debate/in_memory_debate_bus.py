"""In-memory asyncio-based pub/sub for debate events."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from daily_scheduler.domain.ports.debate_bus import DebateBusPort, DebateEvent

__all__ = ["DebateEvent", "InMemoryDebateBus"]


class InMemoryDebateBus(DebateBusPort):
    """Process-local pub/sub keyed by debate_id, backed by asyncio.Queue."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[DebateEvent]]] = defaultdict(list)

    def publish(self, debate_id: str, event: DebateEvent) -> None:
        """Deliver ``event`` to every queue currently subscribed to ``debate_id``."""
        for queue in list(self._subscribers.get(debate_id, [])):
            queue.put_nowait(event)

    def subscribe(self, debate_id: str) -> AsyncIterator[DebateEvent]:
        """Return an async iterator over events published to ``debate_id``.

        The returned async generator is independent of when ``subscribe`` is
        called; subscription registration happens lazily on the first
        iteration so the iterator can be created from sync context (as the
        protocol allows) and consumed from async context.
        """
        queue: asyncio.Queue[DebateEvent] = asyncio.Queue()
        self._subscribers[debate_id].append(queue)

        async def _iter() -> AsyncIterator[DebateEvent]:
            try:
                while True:
                    event = await queue.get()
                    yield event
            finally:
                self._subscribers[debate_id].remove(queue)
                if not self._subscribers[debate_id]:
                    del self._subscribers[debate_id]

        return _iter()
