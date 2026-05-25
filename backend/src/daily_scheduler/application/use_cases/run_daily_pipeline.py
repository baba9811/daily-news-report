"""Use case: orchestrate the full daily report pipeline."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from daily_scheduler import tz
from daily_scheduler.application.use_cases.build_retrospective import (
    BuildRetrospective,
)
from daily_scheduler.application.use_cases.check_recommendations import (
    CheckRecommendations,
)
from daily_scheduler.application.use_cases.fetch_market_data import (
    FetchMarketData,
)
from daily_scheduler.application.use_cases.update_prices import (
    UpdatePrices,
)
from daily_scheduler.domain.entities.market_context import MarketContext
from daily_scheduler.domain.entities.recommendation import (
    Recommendation,
)
from daily_scheduler.domain.entities.report import Report
from daily_scheduler.domain.ports.email_sender import EmailSenderPort
from daily_scheduler.domain.ports.finance_provider import (
    FinanceProviderPort,
)
from daily_scheduler.domain.ports.memory_store import MemoryStorePort
from daily_scheduler.domain.ports.news_provider import NewsProviderPort
from daily_scheduler.domain.ports.price_repository import (
    PriceRepositoryPort,
)
from daily_scheduler.domain.ports.recommendation_repository import (
    RecommendationRepositoryPort,
)
from daily_scheduler.domain.ports.report_renderer import (
    ReportRendererPort,
)
from daily_scheduler.domain.ports.report_repository import (
    ReportRepositoryPort,
)
from daily_scheduler.domain.ports.retrospective_repository import (
    RetrospectiveRepositoryPort,
)
from daily_scheduler.infrastructure.adapters.claude.parser import (
    extract_html_report,
    extract_recommendations,
    extract_summary,
    parse_report_content,
    recommendations_from_content,
)

logger = logging.getLogger(__name__)


class RunDailyPipeline:
    """Orchestrate the full daily report generation pipeline."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        report_repo: ReportRepositoryPort,
        rec_repo: RecommendationRepositoryPort,
        retro_repo: RetrospectiveRepositoryPort,
        price_repo: PriceRepositoryPort,
        finance: FinanceProviderPort,
        news: NewsProviderPort,
        email: EmailSenderPort,
        renderer: ReportRendererPort,
        *,
        memory_store: MemoryStorePort | None = None,
    ) -> None:
        self._report_repo = report_repo
        self._rec_repo = rec_repo
        self._retro_repo = retro_repo
        self._price_repo = price_repo
        self._finance = finance
        self._news = news
        self._email = email
        self._renderer = renderer
        self._memory_store = memory_store

    def execute(self) -> bool:
        """Run the full pipeline. Returns True on success."""
        today = tz.today()

        # Idempotency check
        existing = self._report_repo.get_by_date(
            today,
            "daily",
        )
        if existing:
            logger.info(
                "Daily report for %s already exists (id=%d). Skipping.",
                today,
                existing.id,
            )
            return True

        try:
            return self._run(today)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Daily pipeline failed")
            self._email.send_error("Daily pipeline encountered an unexpected error. Check logs.")
            return False

    def _run(self, today: date) -> bool:
        steps = [
            "Check recommendations",
            "Update prices",
            "Build retrospective",
            "Fetch market data",
            "Screen stock universe",
            "Generate report",
            "Parse report",
            "Save report",
            "Send email",
        ]
        total = len(steps)

        def _step(idx: int) -> str:
            return f"Step {idx}/{total}: {steps[idx - 1]}"

        # 1. Check recommendations (expiry, target/stop)
        logger.info(_step(1))
        CheckRecommendations(
            self._rec_repo,
            self._finance,
            memory_store=self._memory_store,
        ).execute()

        # 2. Update prices for open recommendations
        logger.info(_step(2))
        updated = UpdatePrices(self._rec_repo, self._price_repo, self._finance).execute()
        logger.info("Updated %d recommendations", updated)

        # 3. Build retrospective context and persist
        logger.info(_step(3))
        retro_builder = BuildRetrospective(self._rec_repo)
        retro_context, retro = retro_builder.build_daily_context(today)
        self._retro_repo.save(retro)

        weekly_lessons = ""
        if today.weekday() == 0:
            analysis = retro_builder.build_weekly_analysis(today)
            if analysis:
                self._retro_repo.save_weekly(analysis)
                weekly_lessons = analysis.analysis_text
                logger.info("Weekly analysis built for week of %s", analysis.week_start)

        # 4. Fetch real-time market data
        logger.info(_step(4))
        market_ctx = FetchMarketData(self._finance).execute()
        market_data_text = market_ctx.to_prompt_text()
        logger.info(
            "Market data: %d indices, %d FX, %d commodities, %d futures, VIX=%s, %d ETFs",
            len(market_ctx.indices),
            len(market_ctx.fx_rates),
            len(market_ctx.commodities),
            len(market_ctx.futures),
            market_ctx.vix,
            len(market_ctx.sector_etfs),
        )

        # 5. Screen stock universe
        logger.info(_step(5))
        from daily_scheduler.application.use_cases.screen_stocks import ScreenStocks

        screening_result = ScreenStocks().execute()
        screening_text = screening_result.to_prompt_text()
        logger.info(
            "Screened %d KR + %d US stocks (%d errors)",
            len(screening_result.kr_stocks),
            len(screening_result.us_stocks),
            screening_result.screening_errors,
        )

        # 6. Generate report via Claude (JSON output)
        logger.info(_step(6))
        raw_response, gen_time = self._news.generate_daily_report(
            today,
            retro_context,
            weekly_lessons,
            market_data=market_data_text,
            screening_data=screening_text,
        )

        if not raw_response:
            logger.error("Claude returned empty response. Sending error notification.")
            self._email.send_error("Claude CLI returned empty response for daily report.")
            return False

        # 7. Parse response (JSON → HTML, with legacy fallback)
        logger.info(_step(7))
        html_content, summary, rec_data = self._parse_response(raw_response, market_ctx)

        # 8. Save report + recommendations
        logger.info(_step(8))
        saved_report = self._save_report(today, html_content, summary, raw_response, gen_time)
        self._save_recommendations(saved_report.id, rec_data)  # type: ignore[arg-type]
        self._save_html(today, html_content)

        # 9. Send email
        logger.info(_step(9))
        email_sent = self._email.send(
            f"[{today}] Daily News & Trading Report",
            html_content,
        )
        if not email_sent:
            logger.warning("Email sending failed, but report was saved successfully")

        logger.info("Daily pipeline completed successfully!")
        return True

    def _parse_response(
        self,
        raw_response: str,
        market_ctx: MarketContext,
    ) -> tuple[str, str, list[dict]]:
        """Parse Claude response into (html, summary, rec_data)."""
        report_content = parse_report_content(raw_response)
        if report_content is not None:
            logger.info("JSON parse succeeded — rendering HTML from template")
            from daily_scheduler.config import get_settings

            html_content = self._renderer.render_daily_report(
                report_content,
                market=market_ctx,
                language=get_settings().report_language,
            )
            summary = report_content.market_summary[:200]
            rec_data = recommendations_from_content(report_content)
        else:
            logger.warning("JSON parse failed — falling back to legacy HTML extraction")
            html_content = extract_html_report(raw_response)
            summary = extract_summary(raw_response)
            rec_data = extract_recommendations(raw_response)
        return html_content, summary, rec_data

    def _save_report(
        self,
        today: date,
        html_content: str,
        summary: str,
        raw_response: str,
        gen_time: float,
    ) -> Report:
        """Save report to the database and return the saved report."""
        report = Report(
            report_date=today,
            report_type="daily",
            html_content=html_content,
            summary=summary,
            prompt_used="",
            raw_response=raw_response,
            generation_time_s=gen_time,
        )
        saved_report = self._report_repo.save(report)
        if saved_report.id is None:
            raise RuntimeError("Report save did not return an ID")
        return saved_report

    def _save_recommendations(self, report_id: int, rec_data: list[dict]) -> None:
        """Build Recommendation entities from dicts and persist them."""
        recs = [
            Recommendation(
                report_id=report_id,
                ticker=r.get("ticker", ""),
                name=r.get("name", ""),
                market=r.get("market", ""),
                direction=r.get("direction", "LONG"),
                timeframe=r.get("timeframe", "SWING"),
                entry_price=float(r.get("entry_price", 0)),
                target_price=float(r.get("target_price", 0)),
                stop_loss=float(r.get("stop_loss", 0)),
                rationale=r.get("rationale", ""),
                sector=r.get("sector", ""),
            )
            for r in rec_data
        ]
        if recs:
            self._rec_repo.save_many(recs)
        logger.info("Saved report (id=%d) with %d recommendations", report_id, len(recs))

    @staticmethod
    def _save_html(today: date, html_content: str) -> None:
        from daily_scheduler.config import get_settings

        settings = get_settings()
        db_url = settings.database_url
        reports_dir = Path(db_url.replace("sqlite:///", "")).parent / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"{today}_daily.html"
        path.write_text(html_content, encoding="utf-8")
        logger.info("Report saved to %s", path)
