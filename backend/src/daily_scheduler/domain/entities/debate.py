"""Debate-side domain entities: DebateGraph, Round, Speech, Verdict, ConsensusScore."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from daily_scheduler.domain.entities.agent import Role


class DebateState(StrEnum):
    RUNNING = "RUNNING"
    CONVERGED = "CONVERGED"
    MAX_ROUNDS_DISSENT = "MAX_ROUNDS_DISSENT"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class Speech:
    agent_role: Role
    text: str
    structured_json: dict[str, Any]
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cli_command_hash: str


@dataclass(frozen=True, slots=True)
class ConsensusScore:
    rule_score: float
    llm_score: float
    false_consensus: bool
    next_round_questions: list[str]
    dimensions: dict[str, float]

    def converged(self, *, rule_threshold: float, llm_threshold: float) -> bool:
        if self.false_consensus:
            return False
        return self.rule_score >= rule_threshold and self.llm_score >= llm_threshold


@dataclass(frozen=True, slots=True)
class Round:
    index: int
    bull_speech: Speech
    bear_speech: Speech
    judge_score: ConsensusScore

    @property
    def converged(self) -> bool:
        # Convergence is determined by the engine using thresholds; this is a
        # convenience check assuming default thresholds.
        return self.judge_score.converged(rule_threshold=0.75, llm_threshold=0.70)


@dataclass(frozen=True, slots=True)
class Verdict:
    debate_id: str
    consensus: DebateState
    report_content_json: dict[str, Any]
    recommendation_dicts: list[dict[str, Any]]


@dataclass
class DebateGraph:
    id: str
    pipeline: str
    state: DebateState
    rounds: list[Round]
    analyst_reports: list[dict[str, Any]]
    verdict: Verdict | None
    started_at: datetime
    ended_at: datetime | None
    triggered_by: str  # "scheduler" | "manual" | "multica"
    error: str | None = None
