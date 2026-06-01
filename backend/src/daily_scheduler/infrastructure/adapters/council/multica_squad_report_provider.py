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

_LANGUAGE_NAMES: dict[str, str] = {
    "ko": "Korean (한국어)",
    "en": "English",
    "ja": "Japanese (日本語)",
}

# The EXACT report JSON skeleton the squad leader must fill. Field names, types and
# nesting MUST match parse_report_content (entry_price/target_price/stop_loss,
# probability, technicals & sentiment as LISTS, etc.); a loose field list produced
# mismatched keys (zero prices, empty cells). <prose> values go in the report language.
_REPORT_JSON_SKELETON = """{
  "report_date": "YYYY-MM-DD",
  "market_summary": "<prose>",
  "alert_banner": "<one-line alert>",
  "news_items": [{"category": "", "headline": "<prose>", "source": "", "published_at": "YYYY-MM-DD", "summary": "<prose>", "impact_level": "high|medium|low", "affected_sectors": ["", ""]}],
  "causal_chains": [{"title": "<prose>", "trigger": "<prose>", "chain": [{"step": "<prose>"}], "trading_implication": "<prose>"}],
  "risk_matrix": [{"risk": "<prose>", "probability": "high|medium|low", "impact": "high|medium|low", "mitigation": "<prose>"}],
  "sector_analysis": [{"sector": "<prose>", "etf_ticker": "", "change_percent": 0.0, "volume_vs_avg": 1.0, "signal": "bullish|neutral|bearish"}],
  "sentiment": [{"name": "<indicator>", "value": 0.0, "interpretation": "<prose>", "trend": "up|stable|down"}],
  "technicals": [{"ticker": "", "name": "", "rsi_14": 0.0, "macd_signal": "bullish|bearish|neutral", "above_50d_ma": true, "above_200d_ma": true, "volume_ratio": 1.0, "week_52_high": 0.0, "week_52_low": 0.0, "pct_from_52w_high": 0.0}],
  "recommendations": [{"ticker": "", "name": "", "market": "KOSPI|KOSDAQ|NYSE|NASDAQ", "direction": "LONG|SHORT", "timeframe": "", "entry_price": 0.0, "target_price": 0.0, "stop_loss": 0.0, "risk_reward_ratio": 0.0, "sector": "", "rationale": "<prose>", "confidence": "high|medium|low"}],
  "upcoming_events": [{"date": "YYYY-MM-DD", "event": "<prose>", "expected_impact": "high|medium|low", "details": "<prose>"}],
  "past_performance_commentary": "<prose>",
  "disclaimer": "<prose>"
}"""


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
        language: str = "ko",
    ) -> None:
        self._multica = multica
        self._squad_id = squad_id
        self._fallback = fallback
        self._poll = poll_interval_s
        self._timeout = timeout_s
        self._grace = quiescence_grace_s
        self._language = language

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
            try:
                envelope = extract_report_json(comment.content)
                if envelope and parse_report_content(envelope) is not None:
                    return envelope
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("squad comment parse failed (skipping): %s", exc)
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

    def _compose_brief(
        self,
        report_date: date,
        retro: str,
        weekly_lessons: str,
        market_data: str,
        screening: str,
    ) -> str:
        lang = _LANGUAGE_NAMES.get(self._language, self._language)
        return (
            f"# Daily KR+US Trading Report — {report_date.isoformat()}\n\n"
            "Run the Investment Council. Once members have contributed, the "
            "**Portfolio Manager (squad leader)** posts the FINAL report as a SINGLE "
            "fenced ```json block, then sets this issue's status to `in_review`.\n\n"
            f"### Language\nWrite EVERY natural-language value (the `<prose>` fields — "
            "market_summary, alert_banner, headlines, summaries, rationales, "
            f"mitigations, notes, etc.) in **{lang}**. Keep the JSON field NAMES, "
            "tickers, dates and numbers exactly as specified (do not translate keys).\n\n"
            "### Required JSON shape — use these EXACT keys, types and nesting. Do not "
            "rename keys; do not put a single object where a LIST is shown:\n"
            f"```json\n{_REPORT_JSON_SKELETON}\n```\n"
            "Rules: `entry_price`, `target_price`, `stop_loss`, `risk_reward_ratio` "
            "are REAL numbers at the actual price levels (never 0/placeholder). "
            "`technicals` and `sentiment` are LISTS of objects. `risk_matrix` uses "
            "`probability` (not `likelihood`). Provide at least 5 recommendations with "
            "real entry/target/stop. Cover everything a trading desk does EXCEPT "
            "placing live orders. Cite evidence, prefer numbers.\n\n"
            f"## Retrospective\n{retro or '-'}\n\n"
            f"## Weekly lessons\n{weekly_lessons or '-'}\n\n"
            f"## Market data\n{market_data or '-'}\n\n"
            f"## Screening\n{screening or '-'}\n"
        )
