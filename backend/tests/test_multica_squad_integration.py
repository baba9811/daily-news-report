"""Live integration tests for the Multica squad report path.

Run with: uv run pytest tests/test_multica_squad_integration.py -v --integration
Requires the Multica self-host stack up + agents/squad registered
(`make multica-up && make multica-agents-setup`). Skipped by default.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

import pytest

from daily_scheduler.constants import MULTICA_SQUAD_NAME
from daily_scheduler.infrastructure.adapters.multica.http_client import MulticaHTTPClient


def _live_client() -> MulticaHTTPClient | None:
    """Build a MulticaHTTPClient from the project .env, or None if unconfigured."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return None
    env: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            env[key.strip()] = val.split("#", 1)[0].strip()
    base = env.get("MULTICA_BASE_URL", "")
    if not base:
        return None
    return MulticaHTTPClient(
        base_url=base,
        api_token=env.get("MULTICA_API_TOKEN", ""),
        workspace_id=env.get("MULTICA_WORKSPACE_ID", ""),
    )


def _require_live() -> MulticaHTTPClient:
    client = _live_client()
    if client is None or not asyncio.run(client.health()):
        pytest.skip("Multica not reachable (set MULTICA_BASE_URL + run make multica-up)")
    return client


@pytest.mark.integration
def test_resolve_squad_and_read_methods_live() -> None:
    """resolve_squad_id + the read methods work against the live API."""
    client = _require_live()
    squad_id = asyncio.run(client.resolve_squad_id(MULTICA_SQUAD_NAME))
    if not squad_id:
        pytest.skip("Investment Council squad not registered (run make multica-agents-setup)")

    # Create an UNASSIGNED issue so no agent run is triggered, then read it back.
    issue = asyncio.run(
        client.create_issue(
            title=f"[itest] squad client read plumbing {uuid.uuid4().hex[:8]}",
            body="integration test — safe to delete",
            labels=["infra"],
        )
    )
    assert issue is not None and issue.id

    state = asyncio.run(client.get_issue(issue_id=issue.id))
    assert state is not None and state.status

    runs = asyncio.run(client.list_runs(issue_id=issue.id))
    comments = asyncio.run(client.list_comments(issue_id=issue.id))
    assert isinstance(runs, list)
    assert isinstance(comments, list)


@pytest.mark.integration
def test_squad_assignment_dispatches_leader_live() -> None:
    """Assigning an issue to the squad dispatches a leader run (the council runs)."""
    client = _require_live()
    squad_id = asyncio.run(client.resolve_squad_id(MULTICA_SQUAD_NAME))
    if not squad_id:
        pytest.skip("Investment Council squad not registered")

    issue = asyncio.run(
        client.create_issue(
            title=f"[itest] squad dispatch check {uuid.uuid4().hex[:8]}",
            body="In ONE sentence, state today's KOSPI risk bias. Output a "
            'fenced ```json block: {"market_summary": "..."}. No tools, be fast.',
            labels=["daily-report"],
            assignee_id=squad_id,
        )
    )
    # Deterministic: our client assigned the issue to the squad.
    assert issue is not None and issue.id
    assert issue.assignee == squad_id

    # Best-effort: the runtime should pick it up (a run appears or status leaves
    # 'todo'). Skip rather than fail if the runtime is busy/offline — dispatch
    # timing is Multica's responsibility, not our code's.
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        runs = asyncio.run(client.list_runs(issue_id=issue.id))
        state = asyncio.run(client.get_issue(issue_id=issue.id))
        if runs or (state is not None and state.status != "todo"):
            return  # squad picked it up — dispatch confirmed
        time.sleep(5)
    pytest.skip("runtime did not pick up the squad task within 90s (busy/offline)")
