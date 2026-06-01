"""Tests for LLMReportTranslator (best-effort report translation)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from daily_scheduler.infrastructure.adapters.translation.report_translator import (
    LLMReportTranslator,
)

from daily_scheduler.domain.ports.llm_provider import LLMResult

_SRC = json.dumps({"report_date": "2026-06-01", "market_summary": "코스피 강세"})
_TRANSLATED = json.dumps({"report_date": "2026-06-01", "market_summary": "KOSPI rallied"})


def _provider(text: str) -> MagicMock:
    p = MagicMock()
    p.submit = AsyncMock(
        return_value=LLMResult(
            text=text,
            model="sonnet",
            provider="claude-code",
            tokens_in=0,
            tokens_out=0,
            latency_ms=5,
            command_hash="h",
        )
    )
    return p


def test_translate_returns_translated_json_and_prompts_target_language() -> None:
    provider = _provider(_TRANSLATED)
    out = LLMReportTranslator(provider).translate_report(_SRC, target_language="en")
    assert json.loads(out)["market_summary"] == "KOSPI rallied"
    prompt = provider.submit.call_args.args[0]
    assert "English" in prompt or "en" in prompt
    assert "market_summary" in prompt  # the source payload is included


def test_translate_tolerates_fenced_json() -> None:
    provider = _provider(f"```json\n{_TRANSLATED}\n```")
    out = LLMReportTranslator(provider).translate_report(_SRC, target_language="en")
    assert json.loads(out)["market_summary"] == "KOSPI rallied"


def test_empty_input_returns_input_without_calling_provider() -> None:
    provider = _provider(_TRANSLATED)
    assert LLMReportTranslator(provider).translate_report("  ", target_language="en") == "  "
    provider.submit.assert_not_called()


def test_provider_error_returns_original() -> None:
    provider = MagicMock()
    provider.submit = AsyncMock(side_effect=RuntimeError("cli down"))
    assert LLMReportTranslator(provider).translate_report(_SRC, target_language="en") == _SRC


def test_non_json_output_returns_original() -> None:
    provider = _provider("I could not translate this, sorry.")
    assert LLMReportTranslator(provider).translate_report(_SRC, target_language="en") == _SRC
