"""Port for the debate event bus (pub/sub)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class DebateEvent:
    """A single event published on a debate's event stream."""

    kind: str
    payload: dict[str, Any]


class DebateBusPort(Protocol):
    """Pub/sub port for orchestrator-emitted debate lifecycle events."""

    def publish(self, debate_id: str, event: DebateEvent) -> None:
        """Publish ``event`` to all subscribers of ``debate_id``."""

    def subscribe(self, debate_id: str) -> AsyncIterator[DebateEvent]:
        """Return an async iterator yielding events for ``debate_id``."""
