"""Parse structured data from Claude's report output."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from daily_scheduler.constants import SUMMARY_MAX_LENGTH
from daily_scheduler.domain.entities.report_content import (
    CausalChain,
    CausalChainLink,
    NewsItem,
    RecommendationItem,
    ReportContent,
    RiskItem,
    SectorFlow,
    SentimentIndicator,
    TechnicalSnapshot,
    UpcomingEvent,
)

logger = logging.getLogger(__name__)

# ── Patterns ────────────────────────────────────────────────
REC_PATTERN = re.compile(
    r"<!--\s*REC_START\s*(.*?)\s*REC_END\s*-->",
    re.DOTALL,
)

JSON_BLOCK_PATTERN = re.compile(
    r"```json\s*\n?(.*?)\n?\s*```",
    re.DOTALL,
)


# ── New: JSON-based parsing ─────────────────────────────────


def extract_report_json(raw_output: str) -> dict[str, Any] | None:
    """Extract JSON dict from Claude's response.

    Tries ```json``` code block first, then raw JSON parse.
    """
    match = JSON_BLOCK_PATTERN.search(raw_output)
    if match:
        json_str = match.group(1).strip()
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON block: %s", exc)

    # Fallback: try entire output as JSON
    stripped = raw_output.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    logger.warning("No valid JSON found in Claude output")
    return None


def _parse_list(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Safely extract a list of dicts from data."""
    val = data.get(key, [])
    if isinstance(val, list):
        return val
    return []


# Arrow / separator tokens an LLM may use to join a causal chain into one string.
_CHAIN_SPLIT = re.compile(r"\s*(?:→|->|⇒|=>|➔|▶|»)\s*")


def _parse_chain_links(raw_chain: Any) -> list[CausalChainLink]:
    """Normalize a causal chain into CausalChainLink steps.

    Handles three shapes an LLM may emit:
    - list[dict]  → each {"step": "..."}
    - list[str]   → each string is one step
    - str         → a single arrow-joined string (split on →/->/⇒ ...)

    The string case is critical: iterating a raw string yields characters,
    which previously rendered every glyph as its own step.
    """
    if isinstance(raw_chain, str):
        parts = _CHAIN_SPLIT.split(raw_chain)
        return [CausalChainLink(step=p.strip()) for p in parts if p.strip()]
    if isinstance(raw_chain, list):
        links: list[CausalChainLink] = []
        for s in raw_chain:
            if isinstance(s, str):
                step = s.strip()
            elif isinstance(s, dict):
                step = str(s.get("step", "")).strip()
            else:
                step = str(s).strip()
            if step:
                links.append(CausalChainLink(step=step))
        return links
    return []


def parse_report_content(raw_output: str) -> ReportContent | None:
    """Parse Claude's JSON output into a ReportContent dataclass."""
    data = extract_report_json(raw_output)
    if data is None:
        return None

    try:
        return ReportContent(
            report_date=data.get("report_date", ""),
            market_summary=data.get("market_summary", ""),
            alert_banner=data.get("alert_banner", ""),
            news_items=[
                NewsItem(
                    category=n.get("category", ""),
                    headline=n.get("headline", ""),
                    source=n.get("source", ""),
                    published_at=n.get("published_at", ""),
                    summary=n.get("summary", ""),
                    impact_level=n.get("impact_level", "medium"),
                    affected_sectors=n.get("affected_sectors", []),
                )
                for n in _parse_list(data, "news_items")
            ],
            causal_chains=[
                CausalChain(
                    title=c.get("title", "") or c.get("trigger", ""),
                    trigger=c.get("trigger", ""),
                    chain=_parse_chain_links(c.get("chain", [])),
                    trading_implication=(
                        c.get("trading_implication", "") or c.get("trading_implications", "")
                    ),
                )
                for c in _parse_list(data, "causal_chains")
            ],
            risk_matrix=[
                RiskItem(
                    risk=r.get("risk", ""),
                    probability=r.get("probability", "medium"),
                    impact=r.get("impact", "medium"),
                    mitigation=r.get("mitigation", ""),
                )
                for r in _parse_list(data, "risk_matrix")
            ],
            sector_analysis=[
                SectorFlow(
                    sector=s.get("sector", ""),
                    etf_ticker=s.get("etf_ticker", ""),
                    change_percent=float(s.get("change_percent", 0)),
                    volume_vs_avg=float(s.get("volume_vs_avg", 1.0)),
                    signal=s.get("signal", "neutral"),
                )
                for s in _parse_list(data, "sector_analysis")
            ],
            sentiment=[
                SentimentIndicator(
                    name=si.get("name", ""),
                    value=float(si.get("value", 0)),
                    interpretation=si.get("interpretation", "neutral"),
                    trend=si.get("trend", "stable"),
                )
                for si in _parse_list(data, "sentiment")
            ],
            technicals=[
                TechnicalSnapshot(
                    ticker=t.get("ticker", ""),
                    name=t.get("name", ""),
                    rsi_14=t.get("rsi_14"),
                    macd_signal=t.get("macd_signal", "neutral"),
                    above_50d_ma=t.get("above_50d_ma", True),
                    above_200d_ma=t.get("above_200d_ma", True),
                    volume_ratio=float(t.get("volume_ratio", 1.0)),
                    week_52_high=t.get("week_52_high"),
                    week_52_low=t.get("week_52_low"),
                    pct_from_52w_high=t.get("pct_from_52w_high"),
                )
                for t in _parse_list(data, "technicals")
            ],
            recommendations=[
                RecommendationItem(
                    ticker=rec.get("ticker", ""),
                    name=rec.get("name", ""),
                    market=rec.get("market", ""),
                    direction=rec.get("direction", "LONG"),
                    timeframe=rec.get("timeframe", "SWING"),
                    entry_price=float(rec.get("entry_price", 0)),
                    target_price=float(rec.get("target_price", 0)),
                    stop_loss=float(rec.get("stop_loss", 0)),
                    sector=rec.get("sector", ""),
                    rationale=rec.get("rationale", ""),
                    causal_chain_summary=rec.get("causal_chain_summary", ""),
                    risk_reward_ratio=float(rec.get("risk_reward_ratio", 0)),
                    confidence=rec.get("confidence", "medium"),
                )
                for rec in _parse_list(data, "recommendations")
            ],
            upcoming_events=[
                UpcomingEvent(
                    date=e.get("date", ""),
                    event=e.get("event", ""),
                    expected_impact=e.get("expected_impact", "medium"),
                    details=e.get("details", ""),
                )
                for e in _parse_list(data, "upcoming_events")
            ],
            past_performance_commentary=data.get("past_performance_commentary", ""),
            disclaimer=data.get("disclaimer", ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.error("Failed to construct ReportContent: %s", exc)
        return None


def recommendations_from_content(
    content: ReportContent,
) -> list[dict[str, Any]]:
    """Convert ReportContent recommendations to dicts for pipeline compatibility."""
    return [
        {
            "ticker": r.ticker,
            "name": r.name,
            "market": r.market,
            "direction": r.direction,
            "timeframe": r.timeframe,
            "entry_price": r.entry_price,
            "target_price": r.target_price,
            "stop_loss": r.stop_loss,
            "sector": r.sector,
            "rationale": r.rationale,
        }
        for r in content.recommendations
    ]


# ── Legacy: HTML-based parsing (kept for backward compat) ───


def extract_recommendations(
    raw_output: str,
) -> list[dict[str, Any]]:
    """Extract recommendation JSON from Claude output (legacy HTML markers)."""
    match = REC_PATTERN.search(raw_output)
    if not match:
        logger.warning("No REC_START/REC_END markers found in Claude output")
        return []

    json_str = match.group(1).strip()
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            return data
        logger.warning("Parsed JSON is not a list: %s", type(data))
        return []
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse recommendation JSON: %s", exc)
        return []


def extract_html_report(raw_output: str) -> str:
    """Extract HTML content from Claude's output (legacy)."""
    html_match = re.search(
        r"(<!DOCTYPE html>.*</html>)",
        raw_output,
        re.DOTALL | re.IGNORECASE,
    )
    if html_match:
        return html_match.group(1)

    if "<div" in raw_output or "<table" in raw_output:
        return raw_output

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        '<head><meta charset="utf-8">'
        "<title>Daily Report</title></head>\n"
        f"<body>{raw_output}</body>\n"
        "</html>"
    )


def extract_summary(raw_output: str) -> str:
    """Extract a brief summary from text content."""
    text = re.sub(r"<[^>]+>", "", raw_output)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > SUMMARY_MAX_LENGTH:
        return text[:SUMMARY_MAX_LENGTH] + "..."
    return text
