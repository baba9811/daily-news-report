"""Tests for SQLiteFTS5Search — BM25-ranked keyword search via FTS5."""

from __future__ import annotations

from datetime import datetime

import pytest
from daily_scheduler.infrastructure.adapters.memory.sqlite_fts5_search import (
    SQLiteFTS5Search,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from daily_scheduler.database import Base
from daily_scheduler.infrastructure.adapters.memory.models import (
    MemoryNodeModel,
    create_memory_fts_table,
)


@pytest.fixture
def fixture():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    create_memory_fts_table(eng)
    return lambda: Session(eng), eng


def _add(session, **kwargs):
    base = dict(
        id="01HXYZ",
        file_path="by-sector/semi/SAMSUNG/2026-05-24.md",
        kind="decision",
        symbol="SAMSUNG",
        sector="semiconductor",
        strategy="DAY",
        outcome=None,
        date="2026-05-24",
        summary="x",
        debate_id=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    base.update(kwargs)
    row = MemoryNodeModel(**base)
    session.add(row)
    return row


def test_index_then_search_returns_ranked(fixture) -> None:
    sf, eng = fixture
    search = SQLiteFTS5Search(engine=eng)
    with sf() as s:
        _add(
            s,
            id="a",
            summary="bull case for SAMSUNG semi",
            file_path="by-sector/semi/SAMSUNG/2026-05-24.md",
        )
        _add(
            s,
            id="b",
            summary="bear case for SK-HYNIX",
            file_path="by-sector/semi/SK-HYNIX/2026-05-24.md",
            symbol="SK-HYNIX",
        )
        s.commit()
        for r in s.query(MemoryNodeModel).all():
            search.index(r, body=f"{r.summary} discussion body")

    hits = search.search("SAMSUNG", limit=10)
    assert len(hits) >= 1
    assert hits[0].id == "a"


def test_search_korean_partial_match(fixture) -> None:
    sf, eng = fixture
    search = SQLiteFTS5Search(engine=eng)
    with sf() as s:
        row = _add(s, summary="삼성전자 4분기 실적 발표")
        s.commit()
        search.index(row, body="삼성전자가 좋은 실적을 발표했다")
    hits = search.search("삼성전자", limit=5)
    assert len(hits) == 1


def test_search_no_match_returns_empty(fixture) -> None:
    sf, eng = fixture
    search = SQLiteFTS5Search(engine=eng)
    hits = search.search("nothingmatches", limit=5)
    assert hits == []


def test_delete_then_search(fixture) -> None:
    sf, eng = fixture
    search = SQLiteFTS5Search(engine=eng)
    with sf() as s:
        row = _add(s, id="x", summary="to be removed")
        s.commit()
        search.index(row, body="remove me later")
    search.delete("x")
    hits = search.search("remove", limit=5)
    assert hits == []


def test_reindex_updates_body(fixture) -> None:
    sf, eng = fixture
    search = SQLiteFTS5Search(engine=eng)
    with sf() as s:
        row = _add(s, id="r")
        s.commit()
        search.index(row, body="original")
        search.index(row, body="replacement")
    hits = search.search("replacement", limit=5)
    assert len(hits) == 1
    assert search.search("original", limit=5) == []
