"""MemoryNode — a single reflection entry (decision / pattern / lesson)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from enum import Enum


class MemoryKind(str, Enum):
    DECISION = "decision"
    PATTERN = "pattern"
    LESSON = "lesson"


_SUMMARY_MAX = 200


@dataclass(frozen=True, slots=True)
class MemoryNode:
    id: str
    kind: MemoryKind
    date: date_type
    summary: str
    body: str
    symbol: str | None
    sector: str | None
    strategy: str | None
    outcome: str | None
    debate_id: str | None

    def __post_init__(self) -> None:
        if len(self.summary) > _SUMMARY_MAX:
            raise ValueError(f"summary too long: {len(self.summary)} > {_SUMMARY_MAX} chars")

    def relative_path(self) -> str:
        if self.kind is MemoryKind.DECISION:
            sector = self.sector or "uncategorized"
            symbol = self.symbol or "general"
            return f"by-sector/{sector}/{symbol}/{self.date.isoformat()}.md"
        if self.kind is MemoryKind.PATTERN:
            slug = (self.summary[:40] or self.id).lower().replace(" ", "-")
            return f"patterns/{slug}.md"
        iso_year, iso_week, _ = self.date.isocalendar()
        return f"lessons/{iso_year}-W{iso_week:02d}.md"

    def frontmatter(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "date": self.date.isoformat(),
            "summary": self.summary,
            "symbol": self.symbol,
            "sector": self.sector,
            "strategy": self.strategy,
            "outcome": self.outcome,
            "debate_id": self.debate_id,
        }
