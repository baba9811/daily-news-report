"""Integration tests for MemoryStore composing markdown + tree + FTS5."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from daily_scheduler.database import Base
from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode
from daily_scheduler.domain.ports.memory_store import MemoryQuery
from daily_scheduler.infrastructure.adapters.memory.json_tree_index import (
    JSONTreeIndex,
)
from daily_scheduler.infrastructure.adapters.memory.markdown_store import (
    MarkdownMemoryStore,
)
from daily_scheduler.infrastructure.adapters.memory.memory_store import MemoryStore
from daily_scheduler.infrastructure.adapters.memory.models import (
    create_memory_fts_table,
)
from daily_scheduler.infrastructure.adapters.memory.sqlite_fts5_search import (
    SQLiteFTS5Search,
)


@pytest.fixture
def store(tmp_path):
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    create_memory_fts_table(eng)

    def sf() -> Session:
        return Session(eng)

    md = MarkdownMemoryStore(root=tmp_path / "memory")
    tree = JSONTreeIndex(session_factory=sf, tree_path=tmp_path / "memory" / "tree.json")
    fts = SQLiteFTS5Search(engine=eng)
    return MemoryStore(markdown=md, tree=tree, fts=fts, session_factory=sf)


def _node(**overrides):
    base = dict(
        id="01HXYZ",
        kind=MemoryKind.DECISION,
        date=date(2026, 5, 24),
        summary="bull rec for SAMSUNG",
        body="Discussion body mentioning semiconductor cycle.",
        symbol="SAMSUNG",
        sector="semiconductor",
        strategy="DAY",
        outcome=None,
        debate_id="d1",
    )
    base.update(overrides)
    return MemoryNode(**base)


def test_ingest_writes_file_and_db_and_fts(store, tmp_path) -> None:
    node = _node()
    store.ingest(node)
    assert (tmp_path / "memory" / node.relative_path()).exists()
    assert (tmp_path / "memory" / "tree.json").exists()
    hits = store.query_keyword("SAMSUNG")
    assert any(h.id == node.id for h in hits)


def test_query_metadata_filters(store) -> None:
    store.ingest(_node(id="01H1", symbol="SAMSUNG"))
    store.ingest(_node(id="01H2", symbol="SK-HYNIX", strategy="SWING"))
    results = store.query_metadata(MemoryQuery(strategy="DAY"))
    ids = {n.id for n in results}
    assert "01H1" in ids
    assert "01H2" not in ids


def test_query_keyword_korean(store) -> None:
    store.ingest(_node(id="01H1", summary="삼성전자 매수 추천", body="실적 호조 예상"))
    hits = store.query_keyword("삼성전자")
    assert any(h.id == "01H1" for h in hits)


def test_update_outcome_propagates(store, tmp_path) -> None:
    node = _node()
    store.ingest(node)
    store.update_outcome(node.id, "TARGET_HIT")
    md_content = (tmp_path / "memory" / node.relative_path()).read_text()
    assert "TARGET_HIT" in md_content
    rows = store.query_metadata(MemoryQuery(symbol="SAMSUNG"))
    assert rows[0].outcome == "TARGET_HIT"


def test_ingest_is_atomic_on_fts_failure(store, tmp_path, monkeypatch) -> None:
    node = _node()

    def boom(*args, **kwargs):
        raise RuntimeError("simulated fts failure")

    monkeypatch.setattr(store._fts, "index", boom)
    with pytest.raises(RuntimeError):
        store.ingest(node)
    assert not (tmp_path / "memory" / node.relative_path()).exists()
    rows = store.query_metadata(MemoryQuery(symbol="SAMSUNG"))
    assert rows == []
