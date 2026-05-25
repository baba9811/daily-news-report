"""Tests for MemoryStorePort interface (shape only)."""

from __future__ import annotations

from daily_scheduler.domain.ports.memory_store import MemoryQuery, MemoryStorePort


def test_memory_store_port_has_required_methods() -> None:
    for m in ("ingest", "query_metadata", "query_keyword", "traverse_tree", "update_outcome"):
        assert hasattr(MemoryStorePort, m), f"missing method: {m}"


def test_memory_query_dataclass() -> None:
    q = MemoryQuery(symbol="SAMSUNG", sector="semiconductor", strategy="DAY")
    assert q.symbol == "SAMSUNG"
    assert q.outcome is None
