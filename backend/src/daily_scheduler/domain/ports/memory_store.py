"""Port for the memory subsystem (Markdown + JSON tree + FTS5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from daily_scheduler.domain.entities.memory_node import MemoryNode


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    symbol: str | None = None
    sector: str | None = None
    strategy: str | None = None
    outcome: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    limit: int = 10


class MemoryStorePort(Protocol):
    def ingest(self, node: MemoryNode) -> None: ...
    def query_metadata(self, q: MemoryQuery) -> list[MemoryNode]: ...
    def query_keyword(self, text: str, limit: int = 10) -> list[MemoryNode]: ...
    def traverse_tree(self, query: str, max_depth: int = 3) -> list[MemoryNode]: ...
    def update_outcome(self, memory_id: str, outcome: str) -> None: ...
