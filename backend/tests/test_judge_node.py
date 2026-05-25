"""Tests for the hybrid Judge node (rule + LLM)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from daily_scheduler.infrastructure.adapters.debate.judge_node import (
    _compute_rule_score,
    _detect_false_consensus_rule,
    run_judge,
)

from daily_scheduler.constants import JUDGE_LLM_THRESHOLD, JUDGE_RULE_THRESHOLD
from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.entities.debate import ConsensusScore, Speech
from daily_scheduler.domain.ports.llm_provider import LLMResult
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

FIXTURES = Path(__file__).parent / "fixtures"


def _speech(role: Role, **structured) -> Speech:
    return Speech(
        agent_role=role,
        text="",
        structured_json=dict(structured),
        tokens_in=0,
        tokens_out=0,
        latency_ms=0,
        cli_command_hash="",
    )


def test_rule_score_perfect_agreement() -> None:
    bull = _speech(Role.BULL, direction="BUY", top_tickers=["005930", "000660"], risk_band="MID")
    bear = _speech(Role.BEAR, direction="BUY", top_tickers=["005930", "000660"], risk_band="MID")
    s = _compute_rule_score(bull, bear, prior_rounds=[])
    assert s >= JUDGE_RULE_THRESHOLD


def test_rule_score_opposite_direction() -> None:
    bull = _speech(Role.BULL, direction="BUY", top_tickers=["005930"], risk_band="LOW")
    bear = _speech(Role.BEAR, direction="SELL", top_tickers=["000660"], risk_band="HIGH")
    s = _compute_rule_score(bull, bear, prior_rounds=[])
    assert s < JUDGE_RULE_THRESHOLD


def test_false_consensus_detected_when_one_side_collapses() -> None:
    """Round N-1: bear spoke 500 chars. Round N: bear speech 100 chars. Same direction now."""
    prev_bear = _speech(Role.BEAR, direction="SELL")
    prev_bear = Speech(
        agent_role=prev_bear.agent_role,
        text="x" * 500,
        structured_json=prev_bear.structured_json,
        tokens_in=0,
        tokens_out=0,
        latency_ms=0,
        cli_command_hash="",
    )
    prev_bull = _speech(Role.BULL, direction="BUY")
    from daily_scheduler.domain.entities.debate import Round

    prior = Round(
        index=0,
        bull_speech=prev_bull,
        bear_speech=prev_bear,
        judge_score=ConsensusScore(
            rule_score=0.3,
            llm_score=0.3,
            false_consensus=False,
            next_round_questions=[],
            dimensions={},
        ),
    )

    curr_bear = Speech(
        agent_role=Role.BEAR,
        text="x" * 50,  # >40% shorter
        structured_json={"direction": "BUY"},
        tokens_in=0,
        tokens_out=0,
        latency_ms=0,
        cli_command_hash="",
    )
    curr_bull = _speech(Role.BULL, direction="BUY")
    flag = _detect_false_consensus_rule(curr_bull, curr_bear, prior_rounds=[prior])
    assert flag is True


@pytest.mark.asyncio
async def test_run_judge_combines_rule_and_llm_consensus() -> None:
    bull = _speech(Role.BULL, direction="BUY", top_tickers=["005930"], risk_band="MID")
    bear = _speech(Role.BEAR, direction="BUY", top_tickers=["005930"], risk_band="MID")
    llm_envelope = {
        "agreement_score": 0.85,
        "dimensions": {
            "logical_coherence": 0.9,
            "evidence_quality": 0.85,
            "remaining_disagreement": "",
            "sharpening_questions": [],
        },
        "false_consensus_detected": False,
        "false_consensus_reason": None,
    }
    codex = MagicMock()
    codex.submit = AsyncMock(
        return_value=LLMResult(
            text=json.dumps(llm_envelope),
            model="gpt-5-codex",
            provider="codex",
            tokens_in=0,
            tokens_out=0,
            latency_ms=10,
            command_hash="abc",
        )
    )
    claude = MagicMock()
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

    score = await run_judge(
        router=router,
        render_prompt=lambda role, ctx: "p",
        context={},
        bull=bull,
        bear=bear,
        prior_rounds=[],
    )
    assert isinstance(score, ConsensusScore)
    assert score.rule_score >= JUDGE_RULE_THRESHOLD
    assert score.llm_score == 0.85
    assert score.converged(rule_threshold=JUDGE_RULE_THRESHOLD, llm_threshold=JUDGE_LLM_THRESHOLD)


@pytest.mark.asyncio
async def test_run_judge_blocks_on_llm_false_consensus() -> None:
    bull = _speech(Role.BULL, direction="BUY", top_tickers=["005930"], risk_band="MID")
    bear = _speech(Role.BEAR, direction="BUY", top_tickers=["005930"], risk_band="MID")
    llm_envelope = {
        "agreement_score": 0.95,
        "dimensions": {
            "logical_coherence": 1.0,
            "evidence_quality": 0.9,
            "remaining_disagreement": "",
            "sharpening_questions": ["why did bear flip?"],
        },
        "false_consensus_detected": True,
        "false_consensus_reason": "bear collapsed to bull view without new evidence",
    }
    codex = MagicMock()
    codex.submit = AsyncMock(
        return_value=LLMResult(
            text=json.dumps(llm_envelope),
            model="gpt-5-codex",
            provider="codex",
            tokens_in=0,
            tokens_out=0,
            latency_ms=10,
            command_hash="abc",
        )
    )
    claude = MagicMock()
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

    score = await run_judge(
        router=router,
        render_prompt=lambda r, c: "p",
        context={},
        bull=bull,
        bear=bear,
        prior_rounds=[],
    )
    assert score.false_consensus is True
    assert (
        score.converged(rule_threshold=JUDGE_RULE_THRESHOLD, llm_threshold=JUDGE_LLM_THRESHOLD)
        is False
    )


def test_judge_fixtures_exist() -> None:
    """Three fixture files anchor the judge regression scenarios."""
    assert (FIXTURES / "judge_clear_consensus.json").exists()
    assert (FIXTURES / "judge_clear_dissent.json").exists()
    assert (FIXTURES / "judge_false_consensus.json").exists()
