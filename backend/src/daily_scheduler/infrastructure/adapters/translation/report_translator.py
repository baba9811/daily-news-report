"""LLMReportTranslator — best-effort translation of a report JSON envelope.

Translation runs as one additional LLM pass over the structured report JSON
(the same payload the parser consumes), so the council debate only runs once.
Failures are swallowed and the original JSON is returned, so a translation
outage degrades to a single-language report instead of breaking the pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

from daily_scheduler.constants import TRANSLATION_CLI_TIMEOUT_S
from daily_scheduler.domain.ports.llm_provider import LLMProviderPort
from daily_scheduler.domain.ports.translator import TranslatorPort
from daily_scheduler.infrastructure.adapters.claude.parser import extract_report_json

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "ko": "Korean",
    "ja": "Japanese",
    "zh": "Chinese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}

T = TypeVar("T")


def _run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine from sync code regardless of loop state."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _language_name(code: str) -> str:
    return _LANGUAGE_NAMES.get(code.lower(), code)


def _build_prompt(report_json: str, target_language: str) -> str:
    name = _language_name(target_language)
    return (
        "You are a professional financial translator. Translate every "
        f"natural-language string VALUE in the JSON below into {name}.\n\n"
        "Rules:\n"
        "- Output ONLY the translated JSON object. No prose, no code fences.\n"
        "- Keep the exact same structure and keys.\n"
        "- Do NOT translate JSON keys, ticker symbols (e.g. 005930, NVDA), "
        "numbers, prices, ISO dates, URLs, or short enum tokens (LONG, SHORT, "
        "BUY, SELL, bullish, bearish, neutral, high, medium, low).\n"
        "- Translate prose values: market_summary, alert_banner, headlines, "
        "summaries, rationale, notes, risk and mitigation text, event "
        "descriptions.\n"
        "- Preserve every number, ticker and price exactly as written.\n\n"
        f"JSON:\n{report_json}"
    )


class LLMReportTranslator(TranslatorPort):
    """Translate a report JSON envelope via a subscription-CLI LLM provider."""

    def __init__(
        self,
        provider: LLMProviderPort,
        *,
        model: str = "sonnet",
        timeout_s: int = TRANSLATION_CLI_TIMEOUT_S,
    ) -> None:
        self._provider = provider
        self._model = model
        self._timeout_s = timeout_s

    def translate_report(self, report_json: str, *, target_language: str) -> str:
        if not report_json.strip():
            return report_json
        prompt = _build_prompt(report_json, target_language)
        try:
            result = _run_sync(
                self._provider.submit(
                    prompt,
                    tools=None,
                    timeout_s=self._timeout_s,
                    model=self._model,
                )
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("report translation failed (%s) — keeping original", exc)
            return report_json

        translated = extract_report_json(result.text)
        if translated is None:
            logger.warning("translator returned non-JSON output — keeping original")
            return report_json
        return json.dumps(translated, ensure_ascii=False)
