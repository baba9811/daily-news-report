"""Tests that Verdict serializes to a JSON parseable by parse_report_content."""

from __future__ import annotations

import json

from daily_scheduler.domain.entities.debate import DebateState, Verdict
from daily_scheduler.infrastructure.adapters.claude.parser import parse_report_content
from daily_scheduler.infrastructure.adapters.council.verdict_serializer import (
    verdict_to_report_json,
)


def test_verdict_round_trips_through_existing_parser() -> None:
    payload = {
        "report_date": "2026-05-25",
        "market_summary": "summary",
        "alert_banner": "",
        "news_items": [
            {
                "category": "policy",
                "headline": "h",
                "source": "s",
                "published_at": "2026-05-25",
                "summary": "x",
                "impact_level": "high",
                "affected_sectors": ["semi"],
            }
        ],
        "causal_chains": [],
        "risk_matrix": [],
        "sector_analysis": [],
        "sentiment": [],
        "technicals": [],
        "recommendations": [
            {
                "ticker": "005930",
                "name": "Samsung",
                "market": "KOSPI",
                "direction": "LONG",
                "timeframe": "DAY",
                "entry_price": 70000,
                "target_price": 75000,
                "stop_loss": 68000,
                "sector": "semi",
                "rationale": "x",
                "causal_chain_summary": "y",
                "risk_reward_ratio": 2.5,
                "confidence": "high",
            }
        ],
        "upcoming_events": [],
        "past_performance_commentary": "",
        "disclaimer": "x",
    }
    verdict = Verdict(
        debate_id="d1",
        consensus=DebateState.CONVERGED,
        report_content_json=payload,
        recommendation_dicts=payload["recommendations"],
    )
    raw = verdict_to_report_json(verdict)
    assert isinstance(raw, str)
    parsed = parse_report_content(raw)
    assert parsed is not None
    assert parsed.report_date == "2026-05-25"
    assert len(parsed.recommendations) == 1


def test_verdict_to_report_json_emits_compact_or_indented_json() -> None:
    v = Verdict(
        debate_id="d2",
        consensus=DebateState.CONVERGED,
        report_content_json={"report_date": "2026-05-25"},
        recommendation_dicts=[],
    )
    out = verdict_to_report_json(v)
    assert json.loads(out)["report_date"] == "2026-05-25"
