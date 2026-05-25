"""Port for persisting DebateGraph aggregates."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from daily_scheduler.domain.entities.debate import DebateGraph


class DebateRepositoryPort(Protocol):
    """Persist DebateGraph aggregates and look them up later."""

    def save(self, graph: DebateGraph) -> None:
        """Persist a complete debate aggregate (idempotent on id)."""

    def get(self, debate_id: str) -> DebateGraph | None:
        """Load a single DebateGraph by id, or None if not found."""

    def list_recent(
        self,
        *,
        pipeline: str | None = None,
        limit: int = 50,
    ) -> Iterator[DebateGraph]:
        """Iterate the most recent DebateGraphs (optionally filtered by pipeline)."""
