"""Serializes a Verdict to the JSON shape consumed by the legacy parser.

The output of verdict_to_report_json must round-trip through
daily_scheduler.infrastructure.adapters.claude.parser.parse_report_content
to keep all existing RPT-* acceptance tests passing.
"""

from __future__ import annotations

import json

from daily_scheduler.domain.entities.debate import Verdict


def verdict_to_report_json(verdict: Verdict) -> str:
    """Emit a JSON string matching parse_report_content's expected shape."""
    payload = dict(verdict.report_content_json)
    # Ensure required keys are present (the parser tolerates absence, but
    # downstream renderers may expect them)
    payload.setdefault("report_date", "")
    payload.setdefault("market_summary", "")
    payload.setdefault("alert_banner", "")
    payload.setdefault("news_items", [])
    payload.setdefault("causal_chains", [])
    payload.setdefault("risk_matrix", [])
    payload.setdefault("sector_analysis", [])
    payload.setdefault("sentiment", [])
    payload.setdefault("technicals", [])
    payload.setdefault("recommendations", verdict.recommendation_dicts or [])
    payload.setdefault("upcoming_events", [])
    payload.setdefault("past_performance_commentary", "")
    payload.setdefault("disclaimer", "")
    return json.dumps(payload, ensure_ascii=False)
