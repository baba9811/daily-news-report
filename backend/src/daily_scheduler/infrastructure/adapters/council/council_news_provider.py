"""CouncilNewsProvider — implements NewsProviderPort using the debate engine.

This is the swap-in replacement for ClaudeNewsProvider. The four `generate_*`
methods have identical signatures and return `tuple[str, float]` where the
first element is JSON text that parse_report_content() consumes.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, TypeVar

from daily_scheduler.domain.ports.memory_store import MemoryStorePort
from daily_scheduler.infrastructure.adapters.council.verdict_serializer import (
    verdict_to_report_json,
)
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

T = TypeVar("T")


def _run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from sync code, regardless of loop state.

    - Scheduler/CLI path: no running event loop → asyncio.run is used directly.
    - Test/FastAPI path: a running loop exists in this thread → execute the
      coroutine inside a fresh loop on a worker thread so we don't reuse the
      caller's loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Running loop in this thread — defer to a worker thread.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class CouncilNewsProvider:
    """Multi-agent council that satisfies NewsProviderPort."""

    def __init__(
        self,
        router: LLMRouter,
        memory_store: MemoryStorePort,
    ) -> None:
        self._router = router
        self._memory = memory_store

    def generate_daily_report(
        self,
        report_date: date,
        retrospective_context: str,
        weekly_lessons: str = "",
        market_data: str = "",
        screening_data: str = "",
    ) -> tuple[str, float]:
        return _run_sync(
            self._run_pipeline(
                pipeline="daily",
                context={
                    "date": report_date.isoformat(),
                    "market_data": market_data,
                    "screening": screening_data,
                    "retrospective": retrospective_context,
                    "weekly_lessons": weekly_lessons,
                    "tickers": [],
                    "regime": "neutral",
                },
            )
        )

    def generate_weekly_report(
        self,
        report_date: date,
        weekly_stats: str,
        detailed_performance: str,
        closed_rationales: str = "",
    ) -> tuple[str, float]:
        return _run_sync(
            self._run_pipeline(
                pipeline="weekly",
                context={
                    "date": report_date.isoformat(),
                    "weekly_stats": weekly_stats,
                    "detailed_performance": detailed_performance,
                    "closed_rationales": closed_rationales,
                    "market_data": "",
                    "screening": "",
                    "retrospective": "",
                    "tickers": [],
                    "regime": "weekly",
                },
            )
        )

    def generate_news_briefing(self, report_date: date) -> tuple[str, float]:
        return _run_sync(
            self._run_pipeline(
                pipeline="news",
                context={
                    "date": report_date.isoformat(),
                    "market_data": "",
                    "screening": "",
                    "retrospective": "",
                    "tickers": [],
                    "regime": "kr",
                },
            )
        )

    def generate_global_news_briefing(self, report_date: date) -> tuple[str, float]:
        return _run_sync(
            self._run_pipeline(
                pipeline="global-news",
                context={
                    "date": report_date.isoformat(),
                    "market_data": "",
                    "screening": "",
                    "retrospective": "",
                    "tickers": [],
                    "regime": "us",
                },
            )
        )

    async def _run_pipeline(
        self,
        pipeline: str,
        context: dict,
    ) -> tuple[str, float]:
        from daily_scheduler.application.use_cases.debate_engine import run_debate

        start = time.monotonic()
        graph = await run_debate(
            pipeline=pipeline,
            router=self._router,
            memory_store=self._memory,
            context=context,
            triggered_by="scheduler",
        )
        elapsed = time.monotonic() - start

        if graph.verdict is None:
            # Failed debate — emit a minimal valid envelope so the parser
            # doesn't crash; downstream will see an empty report and a
            # generic error email will be sent by the pipeline as today.
            from daily_scheduler.domain.entities.debate import DebateState, Verdict

            fallback = Verdict(
                debate_id=graph.id,
                consensus=DebateState.FAILED,
                report_content_json={
                    "report_date": context.get("date", ""),
                    "market_summary": f"Debate failed: {graph.error or 'unknown'}",
                },
                recommendation_dicts=[],
            )
            return verdict_to_report_json(fallback), elapsed

        return verdict_to_report_json(graph.verdict), elapsed
