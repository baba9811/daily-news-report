"""Use case: orchestrate a news briefing pipeline (Korean or Global)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path

from daily_scheduler import tz
from daily_scheduler.domain.entities.report import Report
from daily_scheduler.domain.ports.email_sender import EmailSenderPort
from daily_scheduler.domain.ports.report_renderer import ReportRendererPort
from daily_scheduler.domain.ports.report_repository import (
    ReportRepositoryPort,
)
from daily_scheduler.domain.ports.translator import TranslatorPort
from daily_scheduler.infrastructure.adapters.claude.parser import (
    extract_html_report,
    extract_summary,
    parse_report_content,
)

logger = logging.getLogger(__name__)


class RunNewsBriefingPipeline:
    """Orchestrate a news briefing pipeline.

    Parameterized to support both Korean domestic and global international
    briefings through the same pipeline logic.
    """

    def __init__(
        self,
        report_repo: ReportRepositoryPort,
        generate_briefing: Callable[[date], tuple[str, float]],
        email: EmailSenderPort,
        report_type: str,
        email_subject_label: str,
        html_filename_suffix: str,
        renderer: ReportRendererPort | None = None,
        *,
        translator: TranslatorPort | None = None,
        primary_language: str = "ko",
        secondary_language: str = "",
    ) -> None:
        self._report_repo = report_repo
        self._generate_briefing = generate_briefing
        self._email = email
        self._report_type = report_type
        self._email_subject_label = email_subject_label
        self._html_filename_suffix = html_filename_suffix
        self._renderer = renderer
        self._translator = translator
        self._primary_language = primary_language
        self._secondary_language = secondary_language

    def execute(self) -> bool:
        """Run the news briefing pipeline. Returns True on success."""
        today = tz.today()

        # Idempotency check
        existing = self._report_repo.get_by_date(today, self._report_type)
        if existing:
            logger.info(
                "%s for %s already exists (id=%d). Skipping.",
                self._email_subject_label,
                today,
                existing.id,
            )
            return True

        try:
            return self._run(today)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("%s pipeline failed", self._email_subject_label)
            self._email.send_error(
                f"{self._email_subject_label} pipeline encountered an unexpected error. Check logs."
            )
            return False

    def _run(self, today):  # type: ignore[no-untyped-def]
        """Execute the news briefing pipeline steps."""
        # 1. Generate briefing via Claude
        logger.info("Step 1/3: Generate %s", self._email_subject_label)
        raw_response, gen_time = self._generate_briefing(today)

        if not raw_response:
            logger.error("Claude returned empty response. Sending error notification.")
            self._email.send_error(
                f"Claude CLI returned empty response for {self._email_subject_label}."
            )
            return False

        # 2. Render + save report.
        # Council providers return structured JSON; parse it and render via the
        # Jinja2 template (same path as the daily pipeline). Fall back to legacy
        # HTML extraction only when the payload is not parseable JSON — this
        # prevents raw JSON from being dumped into the email <body>.
        logger.info("Step 2/3: Render and save report")
        html_content, summary = self._render(raw_response, today)
        report = Report(
            report_date=today,
            report_type=self._report_type,
            html_content=html_content,
            summary=summary,
            raw_response=raw_response,
            generation_time_s=gen_time,
        )
        saved = self._report_repo.save(report)
        self._save_html(today, html_content)

        # 3. Send email
        logger.info("Step 3/3: Send email")
        email_sent = self._email.send(
            f"[{today}] {self._email_subject_label}",
            html_content,
        )
        if not email_sent:
            logger.warning("Email sending failed, but report was saved successfully")

        # 4. Secondary-language copy (best-effort)
        self._deliver_secondary(saved.id, raw_response, today)

        logger.info("%s pipeline completed successfully!", self._email_subject_label)
        return True

    def _deliver_secondary(self, report_id: int | None, raw_response: str, today: date) -> None:
        """Translate the briefing and deliver it in the secondary language (best-effort)."""
        lang = self._secondary_language
        if not lang or lang == self._primary_language or self._renderer is None:
            return
        from daily_scheduler.application.use_cases.deliver_translation import (
            deliver_translated_report,
        )

        renderer = self._renderer
        deliver_translated_report(
            report_id=report_id,
            raw_response=raw_response,
            report_date=today,
            email_subject=f"[{today}] {self._email_subject_label} ({lang.upper()})",
            target_language=lang,
            translator=self._translator,
            report_repo=self._report_repo,
            email=self._email,
            render=lambda content, language: renderer.render_daily_report(
                content, market=None, language=language
            ),
        )

    def _render(self, raw_response: str, today: date) -> tuple[str, str]:
        """Return (html, summary). Parse JSON + render when possible.

        Falls back to legacy HTML extraction only when the payload cannot be
        parsed as a structured report — avoids dumping raw JSON into the email.
        """
        parsed = parse_report_content(raw_response)
        if parsed is not None and self._renderer is not None:
            from daily_scheduler.config import get_settings

            # News verdicts often omit report_date; fill it for the title.
            if not parsed.report_date:
                parsed.report_date = today.isoformat()
            html = self._renderer.render_daily_report(
                parsed,
                market=None,
                language=get_settings().report_language,
            )
            summary = parsed.market_summary[:200] or extract_summary(raw_response)
            return html, summary
        return extract_html_report(raw_response), extract_summary(raw_response)

    def _save_html(self, today, html_content: str) -> None:
        from daily_scheduler.config import get_settings

        settings = get_settings()
        db_url = settings.database_url
        reports_dir = Path(db_url.replace("sqlite:///", "")).parent / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"{today}_{self._html_filename_suffix}.html"
        path.write_text(html_content, encoding="utf-8")
        logger.info("%s saved to %s", self._email_subject_label, path)


# Backward-compat alias
RunNewsPipeline = RunNewsBriefingPipeline
