"""MulticaSquadReportProvider — runs the daily report through the Multica squad.

Instead of executing the council in-process, this provider creates a Multica
issue assigned to the "Investment Council" squad, lets the Multica runtime
orchestrate the registered agents (leader delegates to members), polls until
the work is quiescent or the issue reaches a terminal status, and extracts the
leader's final fenced-JSON report.

It is robust by construction: any failure (Multica down, squad timeout,
unparseable output) falls back to the in-process ``CouncilReportProvider`` so
the daily email is never silently lost.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from typing import Protocol

from daily_scheduler.domain.ports.multica import MulticaPort
from daily_scheduler.domain.ports.news_provider import NewsProviderPort
from daily_scheduler.infrastructure.adapters.claude.parser import parse_report_content
from daily_scheduler.infrastructure.adapters.council.council_report_provider import (
    _run_sync,
)
from daily_scheduler.infrastructure.adapters.council.report_envelope import (
    extract_report_json,
)

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES: frozenset[str] = frozenset({"in_review", "done"})
_ACTIVE_RUN_STATUSES: frozenset[str] = frozenset({"queued", "running"})


class _ReportFallback(Protocol):
    """The in-process provider used when the squad path cannot deliver."""

    def generate_daily_report(
        self,
        report_date: date,
        retrospective_context: str,
        weekly_lessons: str = "",
        market_data: str = "",
        screening_data: str = "",
    ) -> tuple[str, float]:
        """Generate the daily report in-process (squad fallback)."""

    def generate_weekly_report(
        self,
        report_date: date,
        weekly_stats: str,
        detailed_performance: str,
        closed_rationales: str = "",
    ) -> tuple[str, float]:
        """Generate the weekly retrospective in-process."""


class MulticaSquadReportProvider(NewsProviderPort):
    """Generate the daily report via the Multica Investment Council squad."""

    def __init__(
        self,
        *,
        multica: MulticaPort,
        squad_id: str,
        fallback: _ReportFallback,
        poll_interval_s: int,
        timeout_s: int,
        quiescence_grace_s: int,
    ) -> None:
        self._multica = multica
        self._squad_id = squad_id
        self._fallback = fallback
        self._poll = poll_interval_s
        self._timeout = timeout_s
        self._grace = quiescence_grace_s

    def generate_daily_report(
        self,
        report_date: date,
        retrospective_context: str,
        weekly_lessons: str = "",
        market_data: str = "",
        screening_data: str = "",
    ) -> tuple[str, float]:
        start = time.monotonic()
        raw: str | None = None
        try:
            raw = _run_sync(
                self._run_squad(
                    report_date,
                    retrospective_context,
                    weekly_lessons,
                    market_data,
                    screening_data,
                )
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("multica squad path errored, falling back: %s", exc)
        if raw and parse_report_content(raw) is not None:
            return raw, time.monotonic() - start
        logger.warning("multica squad produced no parseable report — using in-process fallback")
        return self._fallback.generate_daily_report(
            report_date,
            retrospective_context,
            weekly_lessons,
            market_data,
            screening_data,
        )

    def generate_weekly_report(
        self,
        report_date: date,
        weekly_stats: str,
        detailed_performance: str,
        closed_rationales: str = "",
    ) -> tuple[str, float]:
        # Weekly retrospective stays on the in-process council (design decision).
        return self._fallback.generate_weekly_report(
            report_date,
            weekly_stats,
            detailed_performance,
            closed_rationales,
        )

    async def _run_squad(
        self,
        report_date: date,
        retro: str,
        weekly_lessons: str,
        market_data: str,
        screening: str,
    ) -> str | None:
        if not await self._multica.health():
            return None
        issue = await self._multica.create_issue(
            title=f"[daily-report] {report_date.isoformat()} KR+US trading report",
            body=self._compose_brief(report_date, retro, weekly_lessons, market_data, screening),
            labels=["daily-report"],
            assignee_id=self._squad_id,
        )
        if issue is None or not issue.id:
            return None
        await self._await_completion(issue.id)
        comments = await self._multica.list_comments(issue_id=issue.id)
        # Newest-first: prefer the leader's final synthesis over earlier member posts.
        for comment in reversed(comments):
            envelope = extract_report_json(comment.content)
            if envelope and parse_report_content(envelope) is not None:
                return envelope
        return None

    async def _await_completion(self, issue_id: str) -> None:
        """Block until the squad reaches a terminal status or runs go quiescent."""
        deadline = time.monotonic() + self._timeout
        quiet_since: float | None = None
        while time.monotonic() < deadline:
            state = await self._multica.get_issue(issue_id=issue_id)
            if state is not None and state.status in _TERMINAL_STATUSES:
                return
            runs = await self._multica.list_runs(issue_id=issue_id)
            active = any(r.status in _ACTIVE_RUN_STATUSES for r in runs)
            completed = sum(1 for r in runs if r.status == "completed")
            if not active and completed >= 2:  # at least leader + one member ran
                now = time.monotonic()
                if quiet_since is None:
                    quiet_since = now
                if now - quiet_since >= self._grace:
                    return
            else:
                quiet_since = None
            await asyncio.sleep(self._poll)

    @staticmethod
    def _compose_brief(
        report_date: date,
        retro: str,
        weekly_lessons: str,
        market_data: str,
        screening: str,
    ) -> str:
        return (
            f"# Daily KR+US Trading Report — {report_date.isoformat()}\n\n"
            "Run the Investment Council on this task. The **Portfolio Manager "
            "(squad leader)** must, once members have contributed, post the FINAL "
            "report as a SINGLE fenced ```json block matching this schema and then "
            "set this issue's status to `in_review`:\n\n"
            "`report_date, market_summary, alert_banner, news_items, causal_chains, "
            "risk_matrix, sector_analysis, sentiment, technicals, recommendations "
            "[ticker, name, market, direction, timeframe, entry, target, stop, "
            "rationale], upcoming_events, past_performance_commentary, disclaimer`.\n\n"
            "Cover everything a trading desk does EXCEPT placing live orders. Be "
            "concrete, cite evidence, prefer numbers.\n\n"
            f"## Retrospective\n{retro or '-'}\n\n"
            f"## Weekly lessons\n{weekly_lessons or '-'}\n\n"
            f"## Market data\n{market_data or '-'}\n\n"
            f"## Screening\n{screening or '-'}\n"
        )
