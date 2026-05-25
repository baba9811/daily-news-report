"""Verify run_debate publishes expected events when a bus is provided."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from daily_scheduler.application.use_cases.debate_engine import run_debate
from daily_scheduler.infrastructure.adapters.debate.in_memory_debate_bus import (
    DebateEvent,
    InMemoryDebateBus,
)
from tests.test_graph_builder import _mock_router_for_convergence


@pytest.mark.asyncio
async def test_run_debate_emits_lifecycle_events() -> None:
    bus = InMemoryDebateBus()
    received: list[DebateEvent] = []

    router = _mock_router_for_convergence()
    memory = MagicMock(
        query_metadata=MagicMock(return_value=[]),
        traverse_tree=MagicMock(return_value=[]),
    )

    # Subscribe before running by snooping on the bus's internal dict;
    # the orchestrator assigns the debate_id internally. Since we cannot
    # know it ahead of time, attach a sniff that listens to every published
    # event by wrapping bus.publish.
    real_publish = bus.publish

    def snooping_publish(debate_id: str, event: DebateEvent) -> None:
        received.append(event)
        real_publish(debate_id, event)

    bus.publish = snooping_publish  # type: ignore[method-assign]

    graph = await run_debate(
        pipeline="daily",
        router=router,
        memory_store=memory,
        context={
            "date": "2026-05-25",
            "market_data": "",
            "screening": "",
            "retrospective": "",
            "tickers": [],
            "regime": "neutral",
        },
        triggered_by="test",
        max_rounds=1,
        bus=bus,
    )

    assert graph.id
    kinds = [e.kind for e in received]
    # analyst pool is skipped because tickers is [] and analyst_roles
    # would still match for "daily" — verify expected lifecycle events.
    assert "round_start" in kinds
    assert "round_end" in kinds
    assert "judge_done" in kinds
    assert "phase_change" in kinds
    assert kinds[-1] == "debate_done"


@pytest.mark.asyncio
async def test_run_debate_emits_done_event_in_finally() -> None:
    """Even on the happy path, the final event must be debate_done."""
    bus = InMemoryDebateBus()
    captured: list[DebateEvent] = []
    real_publish = bus.publish

    def snoop(debate_id: str, event: DebateEvent) -> None:
        captured.append(event)
        real_publish(debate_id, event)

    bus.publish = snoop  # type: ignore[method-assign]

    router = _mock_router_for_convergence()
    memory = MagicMock(
        query_metadata=MagicMock(return_value=[]),
        traverse_tree=MagicMock(return_value=[]),
    )
    await run_debate(
        pipeline="news",
        router=router,
        memory_store=memory,
        context={
            "date": "2026-05-25",
            "market_data": "",
            "screening": "",
            "retrospective": "",
            "tickers": [],
            "regime": "neutral",
        },
        triggered_by="test",
        max_rounds=1,
        bus=bus,
    )
    assert captured[-1].kind == "debate_done"
