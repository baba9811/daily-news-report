"""Tests for memory_node ORM model and FTS5 virtual table creation."""

from __future__ import annotations

from datetime import datetime

import pytest
from daily_scheduler.infrastructure.adapters.memory.models import (
    MemoryNodeModel,
    create_memory_fts_table,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from daily_scheduler.database import Base


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    create_memory_fts_table(eng)
    return eng


def test_memory_node_table_round_trip(engine) -> None:
    with Session(engine) as session:
        row = MemoryNodeModel(
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
        session.add(row)
        session.commit()
        fetched = session.get(MemoryNodeModel, "01HXYZ")
        assert fetched is not None
        assert fetched.symbol == "SAMSUNG"


def test_fts5_virtual_table_exists(engine) -> None:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_fts'")
        ).fetchall()
        assert any(r[0] == "memory_fts" for r in rows)


def test_fts5_trigram_tokenizer_recall(engine) -> None:
    """Korean partial-match works with trigram tokenizer."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO memory_fts(rowid, body, summary, symbol, sector) "
                "VALUES (1, '삼성전자가 4분기 실적 발표', '실적 발표 요약', 'SAMSUNG', 'semiconductor')"
            )
        )
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT rowid FROM memory_fts WHERE memory_fts MATCH '삼성전자'")
        ).fetchall()
        assert len(result) == 1
        assert result[0][0] == 1
