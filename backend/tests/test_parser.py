"""Tests for the parser module."""

from __future__ import annotations

import json

from daily_scheduler.infrastructure.adapters.claude.parser import (
    _to_float,
    _to_float_or_none,
    extract_html_report,
    extract_recommendations,
    extract_report_json,
    extract_summary,
    parse_report_content,
    recommendations_from_content,
)


class TestNumericCoercion:
    def test_to_float_tolerates_decoration(self):
        assert _to_float("1.6x") == 1.6
        assert _to_float("150%") == 150.0
        assert _to_float("₩1,234.5") == 1234.5
        assert _to_float("-3.5%") == -3.5
        assert _to_float(7) == 7.0

    def test_to_float_returns_default_on_non_numeric(self):
        assert _to_float("N/A", 1.0) == 1.0
        assert _to_float(True) == 0.0  # bool is not a number here
        assert _to_float([1, 2]) == 0.0
        assert _to_float("", 1.0) == 1.0

    def test_to_float_range_keeps_lower_bound(self):
        assert _to_float("100-110") == 100.0
        assert _to_float("1.5-2.0") == 1.5

    def test_to_float_or_none_preserves_none_for_non_numeric(self):
        # Missing optional metric must read as None, never 0.0.
        for v in (None, True, False, [], {}, "N/A", "-"):
            assert _to_float_or_none(v) is None
        assert _to_float_or_none("55") == 55.0
        assert _to_float_or_none(55) == 55.0


# ── JSON-based parsing tests ────────────────────────────────


SAMPLE_JSON = {
    "report_date": "2026-03-17",
    "market_summary": "Markets rallied on tech earnings.",
    "alert_banner": "",
    "news_items": [
        {
            "category": "tech",
            "headline": "NVIDIA GTC 2026",
            "source": "CNBC",
            "published_at": "2026-03-17 10:00",
            "summary": "AI infrastructure expansion announced.",
            "impact_level": "high",
            "affected_sectors": ["Semiconductor"],
        }
    ],
    "causal_chains": [
        {
            "title": "AI Boom",
            "trigger": "GTC announcement",
            "chain": ["AI capex up", "Memory demand up", "SK Hynix benefits"],
            "trading_implication": "Long semiconductors",
        }
    ],
    "risk_matrix": [
        {"risk": "War escalation", "probability": "medium", "impact": "high", "mitigation": "Hedge"}
    ],
    "sector_analysis": [
        {
            "sector": "Tech",
            "etf_ticker": "XLK",
            "change_percent": 1.5,
            "volume_vs_avg": 1.3,
            "signal": "bullish",
        }
    ],
    "sentiment": [{"name": "VIX", "value": 22.5, "interpretation": "fear", "trend": "rising"}],
    "technicals": [
        {
            "ticker": "NVDA",
            "name": "NVIDIA",
            "rsi_14": 55.0,
            "macd_signal": "bullish_cross",
            "above_50d_ma": True,
            "above_200d_ma": True,
            "volume_ratio": 1.2,
            "week_52_high": 210.0,
            "week_52_low": 80.0,
            "pct_from_52w_high": -14.0,
        }
    ],
    "recommendations": [
        {
            "ticker": "NVDA",
            "name": "NVIDIA",
            "market": "NASDAQ",
            "direction": "LONG",
            "timeframe": "SWING",
            "entry_price": 181.0,
            "target_price": 196.0,
            "stop_loss": 174.0,
            "sector": "AI",
            "rationale": "GTC catalyst",
            "causal_chain_summary": "GTC → capex → NVDA",
            "risk_reward_ratio": 2.14,
            "confidence": "high",
        }
    ],
    "upcoming_events": [
        {
            "date": "2026-03-18",
            "event": "FOMC",
            "expected_impact": "high",
            "details": "Rate decision",
        }
    ],
    "past_performance_commentary": "First report",
    "disclaimer": "Not investment advice.",
}


class TestExtractReportJson:
    def test_extracts_json_from_code_block(self):
        raw = f"```json\n{json.dumps(SAMPLE_JSON)}\n```"
        result = extract_report_json(raw)
        assert result is not None
        assert result["report_date"] == "2026-03-17"

    def test_extracts_raw_json(self):
        raw = json.dumps(SAMPLE_JSON)
        result = extract_report_json(raw)
        assert result is not None
        assert result["report_date"] == "2026-03-17"

    def test_returns_none_on_invalid(self):
        result = extract_report_json("This is not JSON at all")
        assert result is None

    def test_returns_none_on_malformed_json(self):
        result = extract_report_json('```json\n{"broken": \n```')
        assert result is None

    def test_ignores_preamble_around_code_block(self):
        raw = f"Here is the report:\n```json\n{json.dumps(SAMPLE_JSON)}\n```\nDone."
        result = extract_report_json(raw)
        assert result is not None


class TestParseReportContent:
    def test_full_parse(self):
        raw = f"```json\n{json.dumps(SAMPLE_JSON)}\n```"
        content = parse_report_content(raw)
        assert content is not None
        assert content.report_date == "2026-03-17"
        assert len(content.news_items) == 1
        assert content.news_items[0].headline == "NVIDIA GTC 2026"
        assert len(content.causal_chains) == 1
        assert len(content.causal_chains[0].chain) == 3
        assert len(content.recommendations) == 1
        assert content.recommendations[0].entry_price == 181.0
        assert content.sentiment[0].value == 22.5
        assert content.technicals[0].rsi_14 == 55.0

    def test_returns_none_on_invalid(self):
        content = parse_report_content("not json")
        assert content is None

    def test_tolerates_analyst_field_aliases_for_sentiment_and_technicals(self):
        """The PM sometimes passes analyst keys (score/source/rsi/vol_ratio)
        straight through; the parser must still populate the tables."""
        payload = {
            "report_date": "2026-06-01",
            "sentiment": [
                {"source": "VIX", "signal": "complacent", "score": 15.78},
            ],
            "technicals": [
                {
                    "ticker": "005930",
                    "rsi": 69,
                    "macd": "momentum",
                    "vol_ratio": 1.6,
                    "ma_status": "above_60ma",
                },
            ],
        }
        raw = f"```json\n{json.dumps(payload)}\n```"
        content = parse_report_content(raw)
        assert content is not None
        assert content.sentiment[0].name == "VIX"
        assert content.sentiment[0].value == 15.78
        assert content.sentiment[0].interpretation == "complacent"
        t = content.technicals[0]
        assert t.rsi_14 == 69.0
        assert t.macd_signal == "momentum"
        assert t.volume_ratio == 1.6
        assert t.above_50d_ma is True

    def test_handles_missing_optional_fields(self):
        minimal = {"report_date": "2026-03-17"}
        raw = f"```json\n{json.dumps(minimal)}\n```"
        content = parse_report_content(raw)
        assert content is not None
        assert content.news_items == []
        assert content.recommendations == []

    def test_tolerates_multiple_and_unit_notation_in_numeric_fields(self):
        """Models often emit '1.6x', '150%', or '₩1,234' for numeric fields.

        These must NOT abort the whole parse (regression: a single '1.6x'
        risk_reward_ratio previously dropped every recommendation).
        """
        payload = {
            "report_date": "2026-06-01",
            "recommendations": [
                {
                    "ticker": "NVDA",
                    "name": "NVIDIA",
                    "entry_price": "₩1,200.50",
                    "target_price": "1,500",
                    "stop_loss": "1100",
                    "risk_reward_ratio": "1.6x",
                }
            ],
            "technicals": [{"ticker": "NVDA", "volume_ratio": "2.3x"}],
            "sector_analysis": [
                {"sector": "Tech", "change_percent": "+1.6%", "volume_vs_avg": "2x"}
            ],
        }
        raw = f"```json\n{json.dumps(payload)}\n```"
        content = parse_report_content(raw)
        assert content is not None
        assert len(content.recommendations) == 1
        rec = content.recommendations[0]
        assert rec.entry_price == 1200.50
        assert rec.target_price == 1500.0
        assert rec.risk_reward_ratio == 1.6
        assert content.technicals[0].volume_ratio == 2.3
        assert content.sector_analysis[0].change_percent == 1.6
        assert content.sector_analysis[0].volume_vs_avg == 2.0


class TestRecommendationsFromContent:
    def test_converts_to_dicts(self):
        raw = f"```json\n{json.dumps(SAMPLE_JSON)}\n```"
        content = parse_report_content(raw)
        assert content is not None
        recs = recommendations_from_content(content)
        assert len(recs) == 1
        assert recs[0]["ticker"] == "NVDA"
        assert recs[0]["entry_price"] == 181.0


# ── Legacy parsing tests ────────────────────────────────────


class TestExtractRecommendations:
    def test_extracts_valid_json(self):
        raw = """
        <html><body>Report</body></html>
        <!-- REC_START
        [
          {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "market": "NASDAQ",
            "direction": "LONG",
            "timeframe": "SWING",
            "entry_price": 185.0,
            "target_price": 195.0,
            "stop_loss": 180.0,
            "sector": "Technology",
            "rationale": "Strong earnings"
          }
        ]
        REC_END -->
        """
        recs = extract_recommendations(raw)
        assert len(recs) == 1
        assert recs[0]["ticker"] == "AAPL"
        assert recs[0]["entry_price"] == 185.0

    def test_returns_empty_on_no_markers(self):
        recs = extract_recommendations("<html>no markers</html>")
        assert recs == []

    def test_returns_empty_on_invalid_json(self):
        raw = "<!-- REC_START\n{invalid}\nREC_END -->"
        recs = extract_recommendations(raw)
        assert recs == []

    def test_multiple_recommendations(self):
        raw = """<!-- REC_START
        [
          {"ticker": "AAPL", "name": "Apple",
           "market": "NASDAQ", "direction": "LONG",
           "timeframe": "DAY", "entry_price": 185,
           "target_price": 190, "stop_loss": 182,
           "sector": "Tech", "rationale": "test"},
          {"ticker": "TSLA", "name": "Tesla",
           "market": "NASDAQ", "direction": "SHORT",
           "timeframe": "SWING", "entry_price": 250,
           "target_price": 230, "stop_loss": 260,
           "sector": "Auto", "rationale": "test2"}
        ]
        REC_END -->"""
        recs = extract_recommendations(raw)
        assert len(recs) == 2
        assert recs[1]["ticker"] == "TSLA"
        assert recs[1]["direction"] == "SHORT"


class TestExtractHtmlReport:
    def test_extracts_full_html_document(self):
        raw = "preamble\n<!DOCTYPE html><html><body>c</body></html>\nmore"
        html = extract_html_report(raw)
        assert html.startswith("<!DOCTYPE html>")
        assert html.endswith("</html>")

    def test_returns_raw_if_html_tags_present(self):
        raw = "<div>content</div><table>data</table>"
        html = extract_html_report(raw)
        assert "<div>" in html

    def test_wraps_plain_text(self):
        raw = "just plain text with no html"
        html = extract_html_report(raw)
        assert "<!DOCTYPE html>" in html
        assert "just plain text" in html


class TestExtractSummary:
    def test_strips_html_and_truncates(self):
        raw = "<h1>Title</h1><p>" + "a" * 300 + "</p>"
        summary = extract_summary(raw)
        assert len(summary) <= 203
        assert "<h1>" not in summary

    def test_short_text_no_ellipsis(self):
        summary = extract_summary("<p>Short text</p>")
        assert summary == "Short text"
        assert "..." not in summary


class TestCausalChainParsing:
    """Regression: causal chain `chain` field arrives in 3 shapes."""

    def test_arrow_joined_string_splits_into_steps(self):
        from daily_scheduler.infrastructure.adapters.claude.parser import (
            parse_report_content,
        )

        raw = json.dumps(
            {
                "report_date": "2026-05-27",
                "causal_chains": [
                    {
                        "trigger": "HBM demand surge",
                        "chain": "HBM 수요 +70% → SK하이닉스 신고가 → KOSPI 사상 최고",
                    }
                ],
            }
        )
        content = parse_report_content(raw)
        assert content is not None
        assert len(content.causal_chains) == 1
        steps = [link.step for link in content.causal_chains[0].chain]
        # 3 steps, NOT one-character-per-step
        assert steps == [
            "HBM 수요 +70%",
            "SK하이닉스 신고가",
            "KOSPI 사상 최고",
        ]

    def test_list_of_strings(self):
        from daily_scheduler.infrastructure.adapters.claude.parser import (
            parse_report_content,
        )

        raw = json.dumps(
            {
                "report_date": "2026-05-27",
                "causal_chains": [{"title": "t", "chain": ["step a", "step b"]}],
            }
        )
        content = parse_report_content(raw)
        assert content is not None
        steps = [link.step for link in content.causal_chains[0].chain]
        assert steps == ["step a", "step b"]

    def test_list_of_dicts(self):
        from daily_scheduler.infrastructure.adapters.claude.parser import (
            parse_report_content,
        )

        raw = json.dumps(
            {
                "report_date": "2026-05-27",
                "causal_chains": [{"title": "t", "chain": [{"step": "one"}, {"step": "two"}]}],
            }
        )
        content = parse_report_content(raw)
        assert content is not None
        steps = [link.step for link in content.causal_chains[0].chain]
        assert steps == ["one", "two"]
