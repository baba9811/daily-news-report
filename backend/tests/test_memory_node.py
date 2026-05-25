"""Tests for MemoryNode domain entity."""

from __future__ import annotations

from datetime import date

import pytest
from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode


def test_memory_node_creates_decision() -> None:
    node = MemoryNode(
        id="01HXYZABCDEF0123456789ABCD",
        kind=MemoryKind.DECISION,
        date=date(2026, 5, 24),
        summary="Bull recommended SAMSUNG; Bear flagged inventory glut",
        body="# Debate digest\n...\n",
        symbol="SAMSUNG",
        sector="semiconductor",
        strategy="DAY",
        outcome=None,
        debate_id="01HABCDEFGH",
    )
    assert node.kind is MemoryKind.DECISION
    assert node.symbol == "SAMSUNG"


def test_summary_max_200_chars() -> None:
    with pytest.raises(ValueError, match="summary"):
        MemoryNode(
            id="01HXYZ",
            kind=MemoryKind.LESSON,
            date=date(2026, 5, 24),
            summary="x" * 201,
            body="",
            symbol=None,
            sector=None,
            strategy=None,
            outcome=None,
            debate_id=None,
        )


def test_kind_enum_values() -> None:
    assert MemoryKind.DECISION.value == "decision"
    assert MemoryKind.PATTERN.value == "pattern"
    assert MemoryKind.LESSON.value == "lesson"


def test_relative_path_for_decision_with_symbol() -> None:
    node = MemoryNode(
        id="01HXYZ",
        kind=MemoryKind.DECISION,
        date=date(2026, 5, 24),
        summary="x",
        body="",
        symbol="SAMSUNG",
        sector="semiconductor",
        strategy="DAY",
        outcome=None,
        debate_id="01HABC",
    )
    assert node.relative_path() == "by-sector/semiconductor/SAMSUNG/2026-05-24.md"


def test_relative_path_for_lesson() -> None:
    node = MemoryNode(
        id="01HXYZ",
        kind=MemoryKind.LESSON,
        date=date(2026, 5, 24),
        summary="x",
        body="",
        symbol=None,
        sector=None,
        strategy=None,
        outcome=None,
        debate_id=None,
    )
    p = node.relative_path()
    assert p.startswith("lessons/2026-W")
    assert p.endswith(".md")


def test_to_frontmatter_dict() -> None:
    node = MemoryNode(
        id="01HXYZ",
        kind=MemoryKind.DECISION,
        date=date(2026, 5, 24),
        summary="s",
        body="",
        symbol="SAMSUNG",
        sector="semiconductor",
        strategy="DAY",
        outcome="TARGET_HIT",
        debate_id="01HABC",
    )
    fm = node.frontmatter()
    assert fm["id"] == "01HXYZ"
    assert fm["kind"] == "decision"
    assert fm["date"] == "2026-05-24"
    assert fm["symbol"] == "SAMSUNG"
    assert fm["outcome"] == "TARGET_HIT"
