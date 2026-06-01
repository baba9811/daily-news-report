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


@dataclass(frozen=True, slots=True)
class MulticaIssueState:
    """A lightweight status snapshot of an issue."""

    id: str
    status: str  # backlog|todo|in_progress|in_review|done|blocked|cancelled


@dataclass(frozen=True, slots=True)
class MulticaComment:
    """A comment posted on an issue (by an agent or a human member)."""

    id: str
    author_type: str  # "agent" | "member"
    author_id: str
    content: str


@dataclass(frozen=True, slots=True)
class MulticaRun:
    """An execution (task run) of an agent against an issue."""

    id: str
    agent_id: str
    kind: str  # "direct" | "comment"
    status: str  # queued|running|completed|failed


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
        assignee_id: str | None = None,
    ) -> MulticaIssue | None:
        """Create a new issue. When ``assignee_id`` is set the issue is assigned
        to a Multica squad. Returns None on disable/failure."""

    async def add_comment(self, *, issue_id: str, body: str) -> bool:
        """Add a comment to an existing issue. Returns False on disable/failure."""

    async def get_issue(self, *, issue_id: str) -> MulticaIssueState | None:
        """Return a status snapshot of an issue. None on disable/failure."""

    async def list_comments(self, *, issue_id: str) -> list[MulticaComment]:
        """Return the issue's comments oldest-first. Empty on disable/failure."""

    async def list_runs(self, *, issue_id: str) -> list[MulticaRun]:
        """Return the issue's agent execution history. Empty on disable/failure."""

    async def health(self) -> bool:
        """Return True when the Multica service is reachable."""
