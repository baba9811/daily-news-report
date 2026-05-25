"""Tests for MarkdownMemoryStore (write/read markdown files with YAML frontmatter)."""

from __future__ import annotations

from datetime import date

import pytest

from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode
from daily_scheduler.infrastructure.adapters.memory.markdown_store import (
    MarkdownMemoryStore,
)


@pytest.fixture
def store(tmp_path):
    return MarkdownMemoryStore(root=tmp_path / "memory")


def _node(**overrides):
    base = dict(
        id="01HXYZ",
        kind=MemoryKind.DECISION,
        date=date(2026, 5, 24),
        summary="Bull recommended SAMSUNG",
        body="# Debate digest\n\nDetails here.\n",
        symbol="SAMSUNG",
        sector="semiconductor",
        strategy="DAY",
        outcome=None,
        debate_id="01HABC",
    )
    base.update(overrides)
    return MemoryNode(**base)


def test_write_creates_file_at_relative_path(store, tmp_path) -> None:
    node = _node()
    store.write(node)
    expected = tmp_path / "memory" / "by-sector" / "semiconductor" / "SAMSUNG" / "2026-05-24.md"
    assert expected.exists()


def test_written_file_has_yaml_frontmatter(store, tmp_path) -> None:
    node = _node()
    store.write(node)
    content = (tmp_path / "memory" / node.relative_path()).read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert "id: 01HXYZ\n" in content
    assert "kind: decision\n" in content
    assert "symbol: SAMSUNG\n" in content
    assert "\n---\n" in content
    assert "# Debate digest" in content


def test_read_round_trips_node(store) -> None:
    node = _node()
    store.write(node)
    loaded = store.read(node.relative_path())
    assert loaded.id == node.id
    assert loaded.kind is MemoryKind.DECISION
    assert loaded.date == date(2026, 5, 24)
    assert loaded.symbol == "SAMSUNG"
    assert loaded.body.strip() == node.body.strip()


def test_update_outcome_rewrites_frontmatter_preserving_body(store) -> None:
    node = _node()
    store.write(node)
    store.update_outcome(node.relative_path(), "TARGET_HIT")
    loaded = store.read(node.relative_path())
    assert loaded.outcome == "TARGET_HIT"
    assert "# Debate digest" in loaded.body


def test_overwrite_is_atomic(store) -> None:
    node1 = _node(body="first")
    node2 = _node(body="second", summary="updated summary")
    store.write(node1)
    store.write(node2)
    loaded = store.read(node1.relative_path())
    assert loaded.body.strip() == "second"
    assert loaded.summary == "updated summary"


def test_root_is_created_lazily(tmp_path) -> None:
    root = tmp_path / "does" / "not" / "exist"
    s = MarkdownMemoryStore(root=root)
    s.write(_node())
    assert root.exists()
