"""Tests for DebateRepository — persists DebateGraph + Round + Speech."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from daily_scheduler.database import Base
from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.entities.debate import (
    ConsensusScore,
    DebateGraph,
    DebateState,
    Round,
    Speech,
    Verdict,
)
from daily_scheduler.infrastructure.adapters.persistence.debate_repository import (
    SQLAlchemyDebateRepository,
)


@pytest.fixture
def session():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        yield s


def _graph_with_round(debate_id: str = "d1") -> DebateGraph:
    bull = Speech(
        agent_role=Role.BULL,
        text="bull says yes",
        structured_json={"direction": "BUY"},
        tokens_in=0,
        tokens_out=0,
        latency_ms=0,
        cli_command_hash="",
    )
    bear = Speech(
        agent_role=Role.BEAR,
        text="bear agrees",
        structured_json={"direction": "BUY"},
        tokens_in=0,
        tokens_out=0,
        latency_ms=0,
        cli_command_hash="",
    )
    score = ConsensusScore(
        rule_score=0.9,
        llm_score=0.85,
        false_consensus=False,
        next_round_questions=[],
        dimensions={"direction": 1.0},
    )
    rnd = Round(index=0, bull_speech=bull, bear_speech=bear, judge_score=score)
    verdict = Verdict(
        debate_id=debate_id,
        consensus=DebateState.CONVERGED,
        report_content_json={"recommendations": [{"ticker": "005930"}]},
        recommendation_dicts=[{"ticker": "005930"}],
    )
    return DebateGraph(
        id=debate_id,
        pipeline="daily",
        state=DebateState.CONVERGED,
        rounds=[rnd],
        analyst_reports=[{"role": "kr_fundamentals"}],
        verdict=verdict,
        started_at=datetime.now(),
        ended_at=datetime.now(),
        triggered_by="scheduler",
    )


def test_save_persists_debate_round_speeches(session) -> None:
    repo = SQLAlchemyDebateRepository(session)
    graph = _graph_with_round()
    repo.save(graph)

    from daily_scheduler.infrastructure.adapters.persistence.models import (
        DebateModel,
        RoundModel,
        SpeechModel,
    )

    assert session.get(DebateModel, "d1") is not None
    assert session.query(RoundModel).count() == 1
    assert session.query(SpeechModel).count() == 2


def test_get_by_id(session) -> None:
    repo = SQLAlchemyDebateRepository(session)
    graph = _graph_with_round()
    repo.save(graph)

    loaded = repo.get("d1")
    assert loaded is not None
    assert loaded.id == "d1"
    assert loaded.state is DebateState.CONVERGED
    assert len(loaded.rounds) == 1
    assert loaded.rounds[0].bull_speech.agent_role is Role.BULL
    assert loaded.rounds[0].bear_speech.agent_role is Role.BEAR


def test_get_returns_none_for_missing(session) -> None:
    repo = SQLAlchemyDebateRepository(session)
    assert repo.get("does-not-exist") is None


def test_list_recent(session) -> None:
    repo = SQLAlchemyDebateRepository(session)
    for i in range(3):
        repo.save(_graph_with_round(f"d{i}"))

    rows = list(repo.list_recent(limit=5))
    assert len(rows) == 3


def test_list_recent_filters_by_pipeline(session) -> None:
    repo = SQLAlchemyDebateRepository(session)
    repo.save(_graph_with_round("daily-1"))

    # Save a news debate too
    news_graph = _graph_with_round("news-1")
    news_graph.pipeline = "news"
    repo.save(news_graph)

    daily_only = list(repo.list_recent(pipeline="daily"))
    news_only = list(repo.list_recent(pipeline="news"))
    assert len(daily_only) == 1
    assert len(news_only) == 1
    assert daily_only[0].pipeline == "daily"
    assert news_only[0].pipeline == "news"


def test_save_is_idempotent_on_same_id(session) -> None:
    repo = SQLAlchemyDebateRepository(session)
    graph = _graph_with_round()
    repo.save(graph)
    # Re-save with the same id should not duplicate the debate row.
    repo.save(graph)

    from daily_scheduler.infrastructure.adapters.persistence.models import DebateModel

    rows = session.query(DebateModel).filter(DebateModel.id == "d1").all()
    assert len(rows) == 1
