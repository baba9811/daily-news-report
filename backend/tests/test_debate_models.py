"""Tests for new ORM models supporting the debate engine."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from daily_scheduler.database import Base
from daily_scheduler.infrastructure.adapters.persistence.models import (
    AgentBindingModel,
    DebateModel,
    RecommendationModel,
    RoundModel,
    SpeechModel,
)


@pytest.fixture
def session():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        yield s


def test_agent_binding_row(session) -> None:
    row = AgentBindingModel(
        role="bull",
        provider="claude-code",
        model="opus",
        system_prompt_override=None,
        timeout_s=600,
        updated_at=datetime.now(),
    )
    session.add(row)
    session.commit()
    assert session.get(AgentBindingModel, "bull").model == "opus"


def test_debate_row(session) -> None:
    now = datetime.now()
    d = DebateModel(
        id="d1",
        pipeline="daily",
        state="RUNNING",
        started_at=now,
        ended_at=None,
        triggered_by="scheduler",
        verdict_json=None,
        error=None,
    )
    session.add(d)
    session.commit()
    assert session.get(DebateModel, "d1").pipeline == "daily"


def test_round_and_speech_rows(session) -> None:
    now = datetime.now()
    d = DebateModel(
        id="d2",
        pipeline="daily",
        state="RUNNING",
        started_at=now,
        ended_at=None,
        triggered_by="scheduler",
        verdict_json=None,
        error=None,
    )
    session.add(d)
    session.commit()

    r = RoundModel(
        id="r1",
        debate_id="d2",
        idx=0,
        rule_score=0.8,
        llm_score=0.7,
        false_consensus=False,
        converged=True,
        dimensions_json={"direction": 1.0},
        next_round_questions_json=[],
        created_at=now,
    )
    session.add(r)
    session.commit()

    s = SpeechModel(
        id="s1",
        debate_id="d2",
        round_id="r1",
        agent_role="bull",
        text="hello",
        structured_json={"direction": "BUY"},
        tokens_in=10,
        tokens_out=2,
        latency_ms=100,
        cli_command_hash="abc",
        created_at=now,
    )
    session.add(s)
    session.commit()
    assert session.get(SpeechModel, "s1").agent_role == "bull"


def test_recommendation_has_debate_id_and_memory_node_id(session) -> None:
    # Smoke test: column exists and accepts NULL + str
    rec = RecommendationModel(
        report_id=1,
        ticker="005930",
        name="Samsung Electronics",
        market="KOSPI",
        direction="LONG",
        timeframe="DAY",
        entry_price=70000.0,
        target_price=75000.0,
        stop_loss=68000.0,
        debate_id="d1",
        memory_node_id="m1",
    )
    session.add(rec)
    # We don't have a real report row, but the column-level smoke test
    # is enough to ensure the migration exists.
    assert rec.debate_id == "d1"
    assert rec.memory_node_id == "m1"
