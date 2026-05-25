"""Tests for debate-side domain entities."""

from __future__ import annotations

from datetime import datetime

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.entities.debate import (
    ConsensusScore,
    DebateGraph,
    DebateState,
    Round,
    Speech,
    Verdict,
)


def test_debate_state_enum() -> None:
    assert DebateState.RUNNING.value == "RUNNING"
    assert DebateState.CONVERGED.value == "CONVERGED"
    assert DebateState.MAX_ROUNDS_DISSENT.value == "MAX_ROUNDS_DISSENT"
    assert DebateState.FAILED.value == "FAILED"


def test_speech_carries_role_and_text() -> None:
    s = Speech(
        agent_role=Role.BULL,
        text="hello",
        structured_json={"direction": "BUY"},
        tokens_in=10,
        tokens_out=2,
        latency_ms=100,
        cli_command_hash="abc123",
    )
    assert s.agent_role is Role.BULL
    assert s.structured_json["direction"] == "BUY"


def test_consensus_score_holds_both_dimensions() -> None:
    c = ConsensusScore(
        rule_score=0.8,
        llm_score=0.75,
        false_consensus=False,
        next_round_questions=["q1", "q2"],
        dimensions={"direction": 1.0, "ticker_overlap": 0.6},
    )
    assert c.rule_score == 0.8
    assert c.converged(rule_threshold=0.75, llm_threshold=0.70)


def test_consensus_score_blocks_on_false_consensus() -> None:
    c = ConsensusScore(
        rule_score=1.0,
        llm_score=1.0,
        false_consensus=True,
        next_round_questions=[],
        dimensions={},
    )
    # Both scores pass but false_consensus blocks
    assert c.converged(rule_threshold=0.75, llm_threshold=0.70) is False


def test_round_carries_two_speeches_and_score() -> None:
    bull = Speech(
        agent_role=Role.BULL,
        text="b",
        structured_json={},
        tokens_in=0,
        tokens_out=0,
        latency_ms=0,
        cli_command_hash="",
    )
    bear = Speech(
        agent_role=Role.BEAR,
        text="r",
        structured_json={},
        tokens_in=0,
        tokens_out=0,
        latency_ms=0,
        cli_command_hash="",
    )
    score = ConsensusScore(
        rule_score=0.5, llm_score=0.5, false_consensus=False, next_round_questions=[], dimensions={}
    )
    r = Round(index=0, bull_speech=bull, bear_speech=bear, judge_score=score)
    assert r.index == 0
    assert r.converged is False


def test_verdict_links_to_debate_and_recommendations() -> None:
    v = Verdict(
        debate_id="d1",
        consensus=DebateState.CONVERGED,
        report_content_json={"market_summary": "x"},
        recommendation_dicts=[{"ticker": "005930", "direction": "LONG"}],
    )
    assert v.debate_id == "d1"
    assert v.consensus is DebateState.CONVERGED
    assert v.report_content_json["market_summary"] == "x"


def test_debate_graph_aggregates_everything() -> None:
    g = DebateGraph(
        id="d1",
        pipeline="daily",
        state=DebateState.RUNNING,
        rounds=[],
        analyst_reports=[],
        verdict=None,
        started_at=datetime.now(),
        ended_at=None,
        triggered_by="scheduler",
    )
    assert g.id == "d1"
    assert g.state is DebateState.RUNNING
    assert g.rounds == []
