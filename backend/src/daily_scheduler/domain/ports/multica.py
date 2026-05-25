"""Port for Multica board interactions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MulticaIssue:
    """An issue created on the Multica board."""

    id: str
    title: str
    labels: tuple[str, ...]
    assignee: str | None


class MulticaPort(Protocol):
    """Outbound port for the Multica board service.

    All implementations MUST be best-effort: failures should not raise out to
    the caller. Disabled (e.g. unset base URL) implementations should return
    falsy/empty results instead of raising.
    """

    async def create_issue(
        self,
        *,
        title: str,
        body: str,
        labels: list[str],
    ) -> MulticaIssue | None:
        """Create a new issue. Returns None on disable/failure."""

    async def add_comment(self, *, issue_id: str, body: str) -> bool:
        """Add a comment to an existing issue. Returns False on disable/failure."""

    async def health(self) -> bool:
        """Return True when the Multica service is reachable."""
