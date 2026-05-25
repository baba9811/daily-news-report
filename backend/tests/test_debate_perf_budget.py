"""Synthetic timing — debate engine should finish well under 20 min with mocks.

The live debate budget is 20 minutes (TEST-05), dominated by real CLI calls.
This test isolates the orchestration layer by mocking the LLM router, so the
remaining time measures only pure Python overhead. A regression here means we
accidentally introduced a non-trivial CPU/IO cost in the orchestration code.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from daily_scheduler.application.use_cases.debate_engine import run_debate

# Reuse the convergence router fixture (already exists, covers all roles).
from tests.test_graph_builder import _mock_router_for_convergence


@pytest.mark.asyncio
async def test_debate_completes_within_budget() -> None:
    """With mocked LLM calls, the daily debate must finish in well under 5 seconds."""
    router = _mock_router_for_convergence()
    memory = MagicMock(
        query_metadata=MagicMock(return_value=[]),
        traverse_tree=MagicMock(return_value=[]),
    )

    start = time.monotonic()
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
        max_rounds=3,
    )
    elapsed = time.monotonic() - start

    # Mocked LLMs return instantly; budget is for live calls (TEST-05).
    # A 5 s ceiling catches accidental sleeps / blocking IO in the orchestrator.
    assert elapsed < 5.0, f"orchestration too slow: {elapsed:.2f}s"
    assert graph.state.value in ("CONVERGED", "MAX_ROUNDS_DISSENT")
