"""Recommendation entity — pure Python dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Recommendation:
    """An individual stock pick from a report."""

    report_id: int
    ticker: str
    name: str
    market: str  # KOSPI, KOSDAQ, NYSE, NASDAQ
    direction: str  # LONG, SHORT
    timeframe: str  # DAY, SWING
    entry_price: float
    target_price: float
    stop_loss: float
    rationale: str = ""
    sector: str = ""
    current_price: float | None = None
    status: str = "OPEN"  # OPEN, TARGET_HIT, STOP_HIT, EXPIRED
    closed_at: datetime | None = None
    closed_price: float | None = None
    pnl_percent: float | None = None
    id: int | None = None
    created_at: datetime | None = field(default=None)
    debate_id: str | None = None
    memory_node_id: str | None = None
