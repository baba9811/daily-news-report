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
    """Safely extract a list of dicts from data.

    LLM/squad output occasionally puts bare strings (or other scalars) where a
    list of objects is expected; those elements are dropped so the per-item
    ``.get`` parsing never crashes the whole report.
    """
    val = data.get(key, [])
    if isinstance(val, list):
        return [item for item in val if isinstance(item, dict)]
    return []


def _parse_dict_list(value: Any, str_key: str) -> list[dict[str, Any]]:
    """Coerce a list into dicts: dicts pass through, non-empty strings become
    ``{str_key: string}`` (preserving content), everything else is dropped."""
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(item)
        elif isinstance(item, str) and item.strip():
            out.append({str_key: item.strip()})
    return out


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


_NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _to_float(value: Any, default: float = 0.0) -> float:
    """Coerce a model-emitted value to ``float``, tolerating decoration.

    Agents frequently write numeric fields as ``"1.6x"``, ``"150%"``,
    ``"₩1,234.5"`` or ``"N/A"``. A bare ``float()`` raises ``ValueError`` on
    these and previously aborted the whole report parse (dropping every
    recommendation). This extracts the first numeric token and returns
    ``default`` when none is present.
    """
    if isinstance(value, bool):  # bool is an int subclass — treat as non-numeric
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return default
    cleaned = value.replace(",", "")
    matches = _NUMERIC_RE.findall(cleaned)
    if not matches:
        return default
    if len(matches) > 1:
        # A range like "1.5-2.0" or "100 to 110" — we keep the first (lower)
        # bound but surface it so silent truncation is observable.
        logger.warning("coerced multi-number value %r to %s", value, matches[0])
    return float(matches[0])


def _to_float_or_none(value: Any) -> float | None:
    """Like ``_to_float`` but preserves ``None``/non-numeric values as ``None``.

    Anything that is not a number or a numeric-bearing string (``None``,
    ``bool``, ``list``, ``dict``, ``"N/A"``) returns ``None`` rather than the
    ``0.0`` default — a missing optional metric must not read as zero.
    """
    if value is None or isinstance(value, (bool, list, dict)):
        return None
    if isinstance(value, str) and not _NUMERIC_RE.search(value.replace(",", "")):
        return None
    return _to_float(value)


def _first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first present, non-None value among ``keys``.

    Tolerates the field-name drift between the analyst agents (``score``,
    ``source``, ``rsi``, ``vol_ratio``) and the report schema (``value``,
    ``name``, ``rsi_14``, ``volume_ratio``) — the Portfolio Manager sometimes
    passes the analyst keys straight through, which would otherwise blank out
    the sentiment and technicals tables.
    """
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _ma_above(snapshot: dict[str, Any], explicit_key: str, *, require_200: bool) -> bool:
    """Resolve an above-MA boolean from an explicit flag or an ``ma_status`` string."""
    explicit = snapshot.get(explicit_key)
    if isinstance(explicit, bool):
        return explicit
    ma_status = str(snapshot.get("ma_status", "")).lower()
    if not ma_status:
        return True
    above = "above" in ma_status
    return (above and "200" in ma_status) if require_200 else above


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
                for c in _parse_dict_list(data.get("causal_chains", []), "title")
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
                    change_percent=_to_float(s.get("change_percent", 0)),
                    volume_vs_avg=_to_float(s.get("volume_vs_avg", 1.0), 1.0),
                    signal=s.get("signal", "neutral"),
                )
                for s in _parse_list(data, "sector_analysis")
            ],
            sentiment=[
                SentimentIndicator(
                    name=str(_first(si, "name", "source", default="")),
                    value=_to_float(_first(si, "value", "score", default=0)),
                    interpretation=str(_first(si, "interpretation", "signal", default="neutral")),
                    trend=str(si.get("trend", "stable")),
                )
                for si in _parse_list(data, "sentiment")
            ],
            technicals=[
                TechnicalSnapshot(
                    ticker=t.get("ticker", ""),
                    name=t.get("name", ""),
                    rsi_14=_to_float_or_none(_first(t, "rsi_14", "rsi")),
                    macd_signal=str(_first(t, "macd_signal", "macd", default="neutral")),
                    above_50d_ma=_ma_above(t, "above_50d_ma", require_200=False),
                    above_200d_ma=_ma_above(t, "above_200d_ma", require_200=True),
                    volume_ratio=_to_float(
                        _first(t, "volume_ratio", "vol_ratio", default=1.0), 1.0
                    ),
                    week_52_high=_to_float_or_none(t.get("week_52_high")),
                    week_52_low=_to_float_or_none(t.get("week_52_low")),
                    pct_from_52w_high=_to_float_or_none(t.get("pct_from_52w_high")),
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
                    entry_price=_to_float(rec.get("entry_price", 0)),
                    target_price=_to_float(rec.get("target_price", 0)),
                    stop_loss=_to_float(rec.get("stop_loss", 0)),
                    sector=rec.get("sector", ""),
                    rationale=rec.get("rationale", ""),
                    causal_chain_summary=rec.get("causal_chain_summary", ""),
                    risk_reward_ratio=_to_float(rec.get("risk_reward_ratio", 0)),
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
