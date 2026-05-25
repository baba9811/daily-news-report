"""Tests for JSONTreeIndex — builds tree.json from memory_node rows."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from daily_scheduler.database import Base
from daily_scheduler.infrastructure.adapters.memory.json_tree_index import (
    JSONTreeIndex,
)
from daily_scheduler.infrastructure.adapters.memory.models import (
    MemoryNodeModel,
    create_memory_fts_table,
)


@pytest.fixture
def session_factory():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    create_memory_fts_table(eng)
    return lambda: Session(eng)


def _row(**overrides):
    base = dict(
        id="01HXYZ",
        file_path="by-sector/semi/SAMSUNG/2026-05-24.md",
        kind="decision",
        symbol="SAMSUNG",
        sector="semiconductor",
        strategy="DAY",
        outcome=None,
        date="2026-05-24",
        summary="bull rec",
        debate_id="01HABC",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    base.update(overrides)
    return MemoryNodeModel(**base)


def test_empty_db_produces_empty_root_children(session_factory, tmp_path) -> None:
    idx = JSONTreeIndex(session_factory=session_factory, tree_path=tmp_path / "tree.json")
    idx.rebuild()
    data = json.loads((tmp_path / "tree.json").read_text())
    # All five top-level branches still exist, but each is empty.
    titles = {c["title"] for c in data["root"]["children"]}
    assert titles == {"by-sector", "by-date", "by-strategy", "patterns", "lessons"}
    for c in data["root"]["children"]:
        assert c["children"] == []


def test_tree_groups_by_sector_then_symbol(session_factory, tmp_path) -> None:
    with session_factory() as s:
        s.add(_row(id="a"))
        s.add(_row(id="b", file_path="by-sector/semi/SK-HYNIX/2026-05-24.md", symbol="SK-HYNIX"))
        s.add(
            _row(
                id="c",
                file_path="by-sector/finance/KB/2026-05-24.md",
                symbol="KB",
                sector="finance",
            )
        )
        s.commit()
    idx = JSONTreeIndex(session_factory=session_factory, tree_path=tmp_path / "tree.json")
    idx.rebuild()
    data = json.loads((tmp_path / "tree.json").read_text())
    by_sector = next(c for c in data["root"]["children"] if c["title"] == "by-sector")
    sectors = {c["title"] for c in by_sector["children"]}
    assert sectors == {"semiconductor", "finance"}


def test_lessons_branch_for_lesson_kind(session_factory, tmp_path) -> None:
    with session_factory() as s:
        s.add(
            _row(
                id="L",
                file_path="lessons/2026-W19.md",
                kind="lesson",
                symbol=None,
                sector=None,
                strategy=None,
            )
        )
        s.commit()
    idx = JSONTreeIndex(session_factory=session_factory, tree_path=tmp_path / "tree.json")
    idx.rebuild()
    data = json.loads((tmp_path / "tree.json").read_text())
    lessons = next(c for c in data["root"]["children"] if c["title"] == "lessons")
    assert len(lessons["children"]) == 1
    assert lessons["children"][0]["file_path"] == "lessons/2026-W19.md"


def test_tree_size_cap_truncates(session_factory, tmp_path) -> None:
    long = "x" * 199
    with session_factory() as s:
        for i in range(200):
            s.add(
                _row(
                    id=f"id{i:03d}",
                    file_path=f"by-sector/s/SYM{i}/2026-05-24.md",
                    summary=long,
                    symbol=f"SYM{i}",
                )
            )
        s.commit()
    idx = JSONTreeIndex(
        session_factory=session_factory,
        tree_path=tmp_path / "tree.json",
        max_bytes=5_000,
    )
    idx.rebuild()
    raw = (tmp_path / "tree.json").read_text()
    assert len(raw.encode("utf-8")) <= 5_500


def test_leaf_includes_summary_outcome_file_path(session_factory, tmp_path) -> None:
    with session_factory() as s:
        s.add(_row(outcome="TARGET_HIT"))
        s.commit()
    idx = JSONTreeIndex(session_factory=session_factory, tree_path=tmp_path / "tree.json")
    idx.rebuild()
    data = json.loads((tmp_path / "tree.json").read_text())
    by_sector = next(c for c in data["root"]["children"] if c["title"] == "by-sector")
    semi = next(c for c in by_sector["children"] if c["title"] == "semiconductor")
    samsung = next(c for c in semi["children"] if c["title"] == "SAMSUNG")
    leaf = samsung["children"][0]
    assert leaf["summary"] == "bull rec"
    assert leaf["outcome"] == "TARGET_HIT"
    assert leaf["file_path"] == "by-sector/semi/SAMSUNG/2026-05-24.md"
