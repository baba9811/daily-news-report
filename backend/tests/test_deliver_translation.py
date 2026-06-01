"""Tests for the deliver_translated_report use case."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

from daily_scheduler.application.use_cases.deliver_translation import (
    deliver_translated_report,
)

_VALID = json.dumps({"report_date": "2026-06-01", "market_summary": "hello", "recommendations": []})


def _call(*, translator, repo, email, render):
    return deliver_translated_report(
        report_id=1,
        raw_response='{"market_summary": "안녕"}',
        report_date=date(2026, 6, 1),
        email_subject="[2026-06-01] Daily Report (EN)",
        target_language="en",
        translator=translator,
        report_repo=repo,
        email=email,
        render=render,
    )


def test_translates_renders_persists_and_emails() -> None:
    translator = MagicMock()
    translator.translate_report.return_value = _VALID
    repo = MagicMock()
    email = MagicMock()
    email.send.return_value = True
    langs: list[str] = []

    def render(_content, language):
        langs.append(language)
        return f"<html>{language}</html>"

    assert _call(translator=translator, repo=repo, email=email, render=render) is True
    translator.translate_report.assert_called_once()
    repo.save_translation.assert_called_once()
    saved = repo.save_translation.call_args.args[0]
    assert saved.language == "en" and saved.html_content == "<html>en</html>"
    email.send.assert_called_once()
    assert langs == ["en"]


def test_disabled_without_translator() -> None:
    repo = MagicMock()
    email = MagicMock()
    assert _call(translator=None, repo=repo, email=email, render=lambda _c, _l: "x") is False
    email.send.assert_not_called()
    repo.save_translation.assert_not_called()


def test_skips_when_translation_unparseable() -> None:
    translator = MagicMock()
    translator.translate_report.return_value = "sorry, cannot translate"
    repo = MagicMock()
    email = MagicMock()
    assert _call(translator=translator, repo=repo, email=email, render=lambda _c, _l: "x") is False
    email.send.assert_not_called()
    repo.save_translation.assert_not_called()
