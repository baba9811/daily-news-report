"""Tests for the squad report-envelope extractor."""

from __future__ import annotations

from daily_scheduler.infrastructure.adapters.council.report_envelope import (
    extract_report_json,
)


def test_extracts_fenced_json() -> None:
    text = 'Here is the report:\n```json\n{"market_summary": "ok"}\n```\nthanks'
    assert extract_report_json(text) == '{"market_summary": "ok"}'


def test_returns_none_without_valid_json() -> None:
    assert extract_report_json("no json here") is None


def test_prefers_last_valid_block() -> None:
    text = '```json\n{"a": 1}\n```\n```json\n{"market_summary": "final"}\n```'
    result = extract_report_json(text)
    assert result is not None and '"final"' in result


def test_falls_back_to_bare_object() -> None:
    text = 'prose {"market_summary": "bare"} more prose'
    assert extract_report_json(text) == '{"market_summary": "bare"}'


def test_skips_unparseable_fenced_block() -> None:
    text = "```json\n{not valid}\n```"
    assert extract_report_json(text) is None
