"""Port for the agent_binding store."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from daily_scheduler.domain.entities.agent import BackendBinding, Role


class AgentBindingRepositoryPort(Protocol):
    """Persistence port for per-role BackendBinding overrides."""

    def get(self, role: Role) -> BackendBinding | None:
        """Return the override for ``role``, or None if no override is stored."""

    def upsert(self, role: Role, binding: BackendBinding) -> None:
        """Insert or update the binding for ``role``."""

    def delete(self, role: Role) -> None:
        """Remove the binding for ``role`` (no-op if absent)."""

    def list_all(self) -> Iterator[tuple[Role, BackendBinding]]:
        """Yield all stored ``(role, binding)`` pairs."""
