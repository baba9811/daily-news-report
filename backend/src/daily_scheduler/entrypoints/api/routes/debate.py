"""Debate API routes — list, detail, and SSE stream endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from daily_scheduler.database import get_db
from daily_scheduler.domain.entities.debate import DebateGraph
from daily_scheduler.infrastructure.adapters.persistence.debate_repository import (
    SQLAlchemyDebateRepository,
)
from daily_scheduler.infrastructure.adapters.sse.sse_broadcaster import (
    make_event_source_response,
)
from daily_scheduler.infrastructure.dependencies import get_debate_bus

router = APIRouter(prefix="/api/debate", tags=["debate"])


@router.get("")
def list_debates(
    pipeline: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List recent debates, optionally filtered by pipeline."""
    repo = SQLAlchemyDebateRepository(db)
    items: list[dict[str, Any]] = []
    for graph in repo.list_recent(pipeline=pipeline, limit=limit):
        items.append(
            {
                "id": graph.id,
                "pipeline": graph.pipeline,
                "state": graph.state.value,
                "started_at": graph.started_at.isoformat() if graph.started_at else None,
                "ended_at": graph.ended_at.isoformat() if graph.ended_at else None,
                "triggered_by": graph.triggered_by,
                "rounds": len(graph.rounds),
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/{debate_id}")
def get_debate(debate_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return the full debate aggregate (rounds + verdict)."""
    repo = SQLAlchemyDebateRepository(db)
    graph = repo.get(debate_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="debate not found")
    return _serialize_debate(graph)


@router.get("/{debate_id}/stream")
async def stream_debate(debate_id: str) -> Any:
    """Stream live debate events as Server-Sent Events."""
    bus = get_debate_bus()
    return make_event_source_response(bus, debate_id)


def _serialize_debate(graph: DebateGraph) -> dict[str, Any]:
    """Convert a DebateGraph aggregate into a JSON-serialisable dict."""
    return {
        "id": graph.id,
        "pipeline": graph.pipeline,
        "state": graph.state.value,
        "started_at": graph.started_at.isoformat() if graph.started_at else None,
        "ended_at": graph.ended_at.isoformat() if graph.ended_at else None,
        "triggered_by": graph.triggered_by,
        "rounds": [
            {
                "index": r.index,
                "bull": {
                    "text": r.bull_speech.text,
                    "structured": r.bull_speech.structured_json,
                    "latency_ms": r.bull_speech.latency_ms,
                },
                "bear": {
                    "text": r.bear_speech.text,
                    "structured": r.bear_speech.structured_json,
                    "latency_ms": r.bear_speech.latency_ms,
                },
                "judge": {
                    "rule_score": r.judge_score.rule_score,
                    "llm_score": r.judge_score.llm_score,
                    "false_consensus": r.judge_score.false_consensus,
                    "dimensions": r.judge_score.dimensions,
                    "next_round_questions": r.judge_score.next_round_questions,
                },
            }
            for r in graph.rounds
        ],
        "verdict": (
            {
                "consensus": graph.verdict.consensus.value,
                "report_content": graph.verdict.report_content_json,
                "recommendations": graph.verdict.recommendation_dicts,
            }
            if graph.verdict
            else None
        ),
        "error": graph.error,
    }
