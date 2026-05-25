"""CouncilNewsProvider — implements NewsProviderPort using the debate engine.

This is the swap-in replacement for ClaudeNewsProvider. The four `generate_*`
methods have identical signatures and return `tuple[str, float]` where the
first element is JSON text that parse_report_content() consumes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, TypeVar

from daily_scheduler.domain.entities.debate import DebateGraph, DebateState
from daily_scheduler.domain.ports.debate_bus import DebateBusPort
from daily_scheduler.domain.ports.debate_repository import DebateRepositoryPort
from daily_scheduler.domain.ports.memory_store import MemoryStorePort
from daily_scheduler.domain.ports.multica import MulticaPort
from daily_scheduler.domain.ports.news_provider import NewsProviderPort
from daily_scheduler.infrastructure.adapters.council.verdict_serializer import (
    verdict_to_report_json,
)
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

_FAILED_DEBATE_STATES: frozenset[DebateState] = frozenset(
    {DebateState.MAX_ROUNDS_DISSENT, DebateState.FAILED}
)

logger = logging.getLogger(__name__)


def _multica_labels_for(state: DebateState) -> list[str]:
    """Return the Multica labels appropriate for a given non-converged state."""
    if state == DebateState.MAX_ROUNDS_DISSENT:
        return ["dissent"]
    return ["infra"]


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


class CouncilNewsProvider(NewsProviderPort):
    """Multi-agent council that satisfies NewsProviderPort."""

    def __init__(
        self,
        router: LLMRouter,
        memory_store: MemoryStorePort,
        debate_repo: DebateRepositoryPort | None = None,
        bus: DebateBusPort | None = None,
        multica: MulticaPort | None = None,
    ) -> None:
        self._router = router
        self._memory = memory_store
        self._debate_repo = debate_repo
        self._bus = bus
        self._multica = multica

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
            bus=self._bus,
        )
        elapsed = time.monotonic() - start

        self._persist_debate(graph)
        await self._notify_multica_on_failure(pipeline=pipeline, graph=graph)

        if graph.verdict is None:
            # Failed debate — emit a minimal valid envelope so the parser
            # doesn't crash; downstream will see an empty report and a
            # generic error email will be sent by the pipeline as today.
            from daily_scheduler.domain.entities.debate import Verdict

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

    def _persist_debate(self, graph: DebateGraph) -> None:
        """Best-effort persistence — failures must not break the report."""
        if self._debate_repo is None:
            return
        try:
            self._debate_repo.save(graph)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("debate persistence failed for %s: %s", graph.id, exc)

    async def _notify_multica_on_failure(self, *, pipeline: str, graph: DebateGraph) -> None:
        """Post an issue to Multica when a debate did not converge.

        Best-effort: any exception is swallowed and logged so a Multica outage
        cannot break the news pipeline.
        """
        if self._multica is None:
            return
        if graph.state not in _FAILED_DEBATE_STATES:
            return
        try:
            await self._multica.create_issue(
                title=f"[{pipeline}] {graph.state.value} {graph.id[:8]}",
                body=(
                    "Debate did not converge.\n"
                    f"rounds: {len(graph.rounds)}\n"
                    f"error: {graph.error or '-'}"
                ),
                labels=_multica_labels_for(graph.state),
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("multica notification failed for debate %s: %s", graph.id, exc)
