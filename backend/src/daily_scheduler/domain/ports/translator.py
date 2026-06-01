"""Port: translate a generated report into another language."""

from __future__ import annotations

from typing import Protocol


class TranslatorPort(Protocol):
    """Translate the natural-language content of a structured report.

    Implementations MUST be best-effort: on any failure they return the input
    JSON unchanged so the pipeline can still deliver the original-language
    report rather than aborting.
    """

    def translate_report(self, report_json: str, *, target_language: str) -> str:
        """Translate the prose string values in a report JSON payload.

        ``report_json`` is the structured report envelope (the same JSON the
        parser consumes). Keys, numbers, tickers, ISO dates and enum tokens are
        preserved; only natural-language values are translated into
        ``target_language`` (an IETF code such as ``"en"``). Returns the
        translated JSON text, or the original on failure.
        """
