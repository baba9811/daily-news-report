"""SQLAlchemy adapter for DebateRepositoryPort."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from sqlalchemy.orm import Session
from ulid import ULID

from daily_scheduler.constants import JUDGE_LLM_THRESHOLD, JUDGE_RULE_THRESHOLD
from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.entities.debate import (
    ConsensusScore,
    DebateGraph,
    DebateState,
    Round,
    Speech,
    Verdict,
)
from daily_scheduler.infrastructure.adapters.persistence.models import (
    DebateModel,
    RoundModel,
    SpeechModel,
)


class SQLAlchemyDebateRepository:
    """Persist DebateGraph aggregates via SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, graph: DebateGraph) -> None:
        """Persist the full DebateGraph (debate row + rounds + speeches)."""
        self._s.merge(
            DebateModel(
                id=graph.id,
                pipeline=graph.pipeline,
                state=graph.state.value,
                started_at=graph.started_at,
                ended_at=graph.ended_at,
                triggered_by=graph.triggered_by,
                verdict_json=(graph.verdict.report_content_json if graph.verdict else None),
                error=graph.error,
            )
        )

        for rnd in graph.rounds:
            round_id = str(ULID())
            self._s.merge(
                RoundModel(
                    id=round_id,
                    debate_id=graph.id,
                    idx=rnd.index,
                    rule_score=rnd.judge_score.rule_score,
                    llm_score=rnd.judge_score.llm_score,
                    false_consensus=rnd.judge_score.false_consensus,
                    converged=rnd.judge_score.converged(
                        rule_threshold=JUDGE_RULE_THRESHOLD,
                        llm_threshold=JUDGE_LLM_THRESHOLD,
                    ),
                    dimensions_json=dict(rnd.judge_score.dimensions),
                    next_round_questions_json=list(rnd.judge_score.next_round_questions),
                    created_at=datetime.now(),
                )
            )
            for speech in (rnd.bull_speech, rnd.bear_speech):
                self._s.add(
                    SpeechModel(
                        id=str(ULID()),
                        debate_id=graph.id,
                        round_id=round_id,
                        agent_role=speech.agent_role.value,
                        text=speech.text,
                        structured_json=dict(speech.structured_json),
                        tokens_in=speech.tokens_in,
                        tokens_out=speech.tokens_out,
                        latency_ms=speech.latency_ms,
                        cli_command_hash=speech.cli_command_hash,
                        created_at=datetime.now(),
                    )
                )
        self._s.commit()

    def get(self, debate_id: str) -> DebateGraph | None:
        """Reconstruct a DebateGraph from the persisted rows."""
        row = self._s.get(DebateModel, debate_id)
        if row is None:
            return None

        rounds = self._load_rounds(debate_id)
        verdict = self._build_verdict(row)
        return DebateGraph(
            id=row.id,
            pipeline=row.pipeline,
            state=DebateState(row.state),
            rounds=rounds,
            analyst_reports=[],
            verdict=verdict,
            started_at=row.started_at,
            ended_at=row.ended_at,
            triggered_by=row.triggered_by,
            error=row.error,
        )

    def list_recent(
        self,
        *,
        pipeline: str | None = None,
        limit: int = 50,
    ) -> Iterator[DebateGraph]:
        """Yield the most recent debates (optionally filtered)."""
        query = self._s.query(DebateModel)
        if pipeline is not None:
            query = query.filter(DebateModel.pipeline == pipeline)
        rows = query.order_by(DebateModel.started_at.desc()).limit(limit).all()
        for row in rows:
            graph = self.get(row.id)
            if graph is not None:
                yield graph

    def _load_rounds(self, debate_id: str) -> list[Round]:
        rounds_rows = (
            self._s.query(RoundModel)
            .filter(RoundModel.debate_id == debate_id)
            .order_by(RoundModel.idx)
            .all()
        )
        rounds: list[Round] = []
        for round_row in rounds_rows:
            speech_rows = (
                self._s.query(SpeechModel).filter(SpeechModel.round_id == round_row.id).all()
            )
            bull = next((s for s in speech_rows if s.agent_role == Role.BULL.value), None)
            bear = next((s for s in speech_rows if s.agent_role == Role.BEAR.value), None)
            if bull is None or bear is None:
                # News pipeline stores Editor/Publisher speeches; map them in.
                bull = bull or next(
                    (s for s in speech_rows if s.agent_role == Role.EDITOR.value),
                    None,
                )
                bear = bear or next(
                    (s for s in speech_rows if s.agent_role == Role.PUBLISHER.value),
                    None,
                )
            if bull is None or bear is None:
                continue
            rounds.append(
                Round(
                    index=round_row.idx,
                    bull_speech=self._row_to_speech(bull),
                    bear_speech=self._row_to_speech(bear),
                    judge_score=ConsensusScore(
                        rule_score=round_row.rule_score,
                        llm_score=round_row.llm_score,
                        false_consensus=round_row.false_consensus,
                        next_round_questions=list(round_row.next_round_questions_json or []),
                        dimensions=dict(round_row.dimensions_json or {}),
                    ),
                )
            )
        return rounds

    @staticmethod
    def _build_verdict(row: DebateModel) -> Verdict | None:
        if row.verdict_json is None:
            return None
        payload = dict(row.verdict_json)
        recs = payload.get("recommendations", [])
        return Verdict(
            debate_id=row.id,
            consensus=DebateState(row.state),
            report_content_json=payload,
            recommendation_dicts=list(recs) if isinstance(recs, list) else [],
        )

    @staticmethod
    def _row_to_speech(row: SpeechModel) -> Speech:
        return Speech(
            agent_role=Role(row.agent_role),
            text=row.text,
            structured_json=dict(row.structured_json or {}),
            tokens_in=row.tokens_in,
            tokens_out=row.tokens_out,
            latency_ms=row.latency_ms,
            cli_command_hash=row.cli_command_hash,
        )
