"""Use case: deliver a translated copy of a report (separate email + storage).

Best-effort by design: a translation/render/email failure is logged and
swallowed so the primary-language report is never put at risk.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from daily_scheduler.domain.entities.report import ReportTranslation
from daily_scheduler.domain.entities.report_content import ReportContent
from daily_scheduler.domain.ports.email_sender import EmailSenderPort
from daily_scheduler.domain.ports.report_repository import ReportRepositoryPort
from daily_scheduler.domain.ports.translator import TranslatorPort
from daily_scheduler.infrastructure.adapters.claude.parser import parse_report_content

logger = logging.getLogger(__name__)


def deliver_translated_report(
    *,
    report_id: int | None,
    raw_response: str,
    report_date: date,
    email_subject: str,
    target_language: str,
    translator: TranslatorPort | None,
    report_repo: ReportRepositoryPort,
    email: EmailSenderPort,
    render: Callable[[ReportContent, str], str],
) -> bool:
    """Translate ``raw_response`` into ``target_language``, persist + email it.

    ``render`` renders a ``ReportContent`` for a given language (the caller
    closes over any market context). Returns True when the translated email was
    sent. Disabled (no translator / blank language / unsaved report) returns
    False silently.
    """
    if translator is None or not target_language or report_id is None:
        return False
    try:
        translated_json = translator.translate_report(raw_response, target_language=target_language)
        content = parse_report_content(translated_json)
        if content is None:
            logger.warning(
                "translated report (%s) did not parse — skipping delivery",
                target_language,
            )
            return False
        if not content.report_date:
            content.report_date = report_date.isoformat()
        html = render(content, target_language)
        summary = (content.market_summary or "")[:200]
        report_repo.save_translation(
            ReportTranslation(
                report_id=report_id,
                language=target_language,
                html_content=html,
                summary=summary,
            )
        )
        sent = email.send(email_subject, html)
        logger.info(
            "Delivered %s translation for report %d (emailed=%s)",
            target_language,
            report_id,
            sent,
        )
        return sent
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("translated report delivery failed: %s", exc)
        return False
