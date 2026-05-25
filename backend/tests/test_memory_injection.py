"""Tests for memory auto-injection."""

from __future__ import annotations

from datetime import date

from daily_scheduler.application.use_cases.memory_injection import (
    build_memory_context,
)
from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode
from daily_scheduler.domain.ports.memory_store import MemoryQuery


class _FakeStore:
    """Minimal in-memory MemoryStorePort double for the injection helper."""

    def __init__(self, nodes: list[MemoryNode]) -> None:
        self._nodes = nodes

    def ingest(self, node: MemoryNode) -> None:  # pragma: no cover - unused here
        self._nodes.append(node)

    def query_metadata(self, q: MemoryQuery) -> list[MemoryNode]:
        return [n for n in self._nodes if q.symbol in (None, n.symbol)]

    def query_keyword(self, text: str, limit: int = 10) -> list[MemoryNode]:
        return [n for n in self._nodes if text in n.summary][:limit]

    def traverse_tree(self, query: str, max_depth: int = 3) -> list[MemoryNode]:  # noqa: ARG002
        return self._nodes[:5]

    def update_outcome(self, memory_id: str, outcome: str) -> None:  # pragma: no cover
        pass


def _node(i: int) -> MemoryNode:
    return MemoryNode(
        id=f"id{i}",
        kind=MemoryKind.DECISION,
        date=date(2026, 5, 24),
        summary=f"summary {i}",
        body="body",
        symbol=f"SYM{i}",
        sector="x",
        strategy="DAY",
        outcome=None,
        debate_id=None,
    )


def test_build_memory_context_returns_top_k() -> None:
    store = _FakeStore([_node(i) for i in range(10)])
    out = build_memory_context(
        store=store,
        tickers=["SYM0", "SYM1"],
        pipeline="daily",
        regime="neutral",
        top_k=5,
    )
    assert len(out) <= 5
    assert all(isinstance(n, MemoryNode) for n in out)


def test_build_memory_context_empty_store_returns_empty() -> None:
    store = _FakeStore([])
    out = build_memory_context(
        store=store,
        tickers=[],
        pipeline="daily",
        regime="neutral",
        top_k=5,
    )
    assert out == []


def test_dedup_preserves_order() -> None:
    repeated = _node(0)

    class Store(_FakeStore):
        def query_metadata(self, q: MemoryQuery) -> list[MemoryNode]:  # noqa: ARG002
            return [repeated, repeated]

        def traverse_tree(self, query: str, max_depth: int = 3) -> list[MemoryNode]:  # noqa: ARG002
            return [repeated]

    store = Store([])
    out = build_memory_context(
        store=store,
        tickers=["SYM0"],
        pipeline="daily",
        regime="x",
        top_k=5,
    )
    assert len(out) == 1
