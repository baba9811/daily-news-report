"""Council should post to Multica when a debate fails to converge."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from daily_scheduler.domain.entities.debate import DebateGraph, DebateState
from daily_scheduler.infrastructure.adapters.council.council_news_provider import (
    CouncilNewsProvider,
)


def _failing_graph(state: DebateState) -> DebateGraph:
    return DebateGraph(
        id="d1deadbeef",
        pipeline="daily",
        state=state,
        rounds=[],
        analyst_reports=[],
        verdict=None,
        started_at=datetime.now(),
        ended_at=datetime.now(),
        triggered_by="test",
        error=None,
    )


@pytest.mark.asyncio
async def test_multica_called_when_debate_dissents(monkeypatch) -> None:
    async def fake_run_debate(**_kwargs):
        return _failing_graph(DebateState.MAX_ROUNDS_DISSENT)

    monkeypatch.setattr(
        "daily_scheduler.application.use_cases.debate_engine.run_debate",
        fake_run_debate,
    )
    multica = MagicMock()
    multica.create_issue = AsyncMock(return_value=None)
    provider = CouncilNewsProvider(
        router=MagicMock(),
        memory_store=MagicMock(
            query_metadata=MagicMock(return_value=[]),
            traverse_tree=MagicMock(return_value=[]),
        ),
        multica=multica,
    )
    await provider._run_pipeline(  # pylint: disable=protected-access
        "daily", {"date": "2026-05-25"}
    )
    multica.create_issue.assert_awaited_once()
    kwargs = multica.create_issue.await_args.kwargs
    assert "dissent" in kwargs["labels"]
    assert "daily" in kwargs["title"]


@pytest.mark.asyncio
async def test_multica_called_when_debate_fails(monkeypatch) -> None:
    async def fake_run_debate(**_kwargs):
        return _failing_graph(DebateState.FAILED)

    monkeypatch.setattr(
        "daily_scheduler.application.use_cases.debate_engine.run_debate",
        fake_run_debate,
    )
    multica = MagicMock()
    multica.create_issue = AsyncMock(return_value=None)
    provider = CouncilNewsProvider(
        router=MagicMock(),
        memory_store=MagicMock(
            query_metadata=MagicMock(return_value=[]),
            traverse_tree=MagicMock(return_value=[]),
        ),
        multica=multica,
    )
    await provider._run_pipeline(  # pylint: disable=protected-access
        "daily", {"date": "2026-05-25"}
    )
    multica.create_issue.assert_awaited_once()
    kwargs = multica.create_issue.await_args.kwargs
    assert "infra" in kwargs["labels"]


@pytest.mark.asyncio
async def test_multica_not_called_when_no_multica_wired(monkeypatch) -> None:
    async def fake_run_debate(**_kwargs):
        return _failing_graph(DebateState.MAX_ROUNDS_DISSENT)

    monkeypatch.setattr(
        "daily_scheduler.application.use_cases.debate_engine.run_debate",
        fake_run_debate,
    )
    provider = CouncilNewsProvider(
        router=MagicMock(),
        memory_store=MagicMock(
            query_metadata=MagicMock(return_value=[]),
            traverse_tree=MagicMock(return_value=[]),
        ),
        multica=None,
    )
    # Must not raise; just falls through with no Multica calls.
    text, _ = await provider._run_pipeline(  # pylint: disable=protected-access
        "daily", {"date": "2026-05-25"}
    )
    assert isinstance(text, str)


@pytest.mark.asyncio
async def test_multica_failure_does_not_break_pipeline(monkeypatch) -> None:
    """A raise inside multica.create_issue must not propagate."""

    async def fake_run_debate(**_kwargs):
        return _failing_graph(DebateState.MAX_ROUNDS_DISSENT)

    monkeypatch.setattr(
        "daily_scheduler.application.use_cases.debate_engine.run_debate",
        fake_run_debate,
    )
    multica = MagicMock()
    multica.create_issue = AsyncMock(side_effect=RuntimeError("multica down"))
    provider = CouncilNewsProvider(
        router=MagicMock(),
        memory_store=MagicMock(
            query_metadata=MagicMock(return_value=[]),
            traverse_tree=MagicMock(return_value=[]),
        ),
        multica=multica,
    )
    text, _ = await provider._run_pipeline(  # pylint: disable=protected-access
        "daily", {"date": "2026-05-25"}
    )
    assert isinstance(text, str)
