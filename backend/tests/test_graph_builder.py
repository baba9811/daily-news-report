"""Smoke tests for graph builder + orchestrator (with stub nodes)."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from daily_scheduler.application.use_cases.debate_engine import run_debate

from daily_scheduler.domain.entities.debate import DebateState
from daily_scheduler.domain.ports.llm_provider import LLMResult
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


def _r(text: str) -> LLMResult:
    return LLMResult(
        text=text,
        model="opus",
        provider="claude-code",
        tokens_in=0,
        tokens_out=0,
        latency_ms=1,
        command_hash="abc",
    )


def _mock_router_for_convergence() -> LLMRouter:
    """All agents agree perfectly → converge in round 1."""
    claude = MagicMock()
    converging_response = {
        "direction": "BUY",
        "top_tickers": ["005930"],
        "risk_band": "MID",
        "argument": "good",
        "evidence": ["e1"],
        "proposals": [{"ticker": "005930"}],
        "decision": "APPROVE",
        "report_date": "2026-05-25",
        "market_summary": "x",
        "alert_banner": "",
        "news_items": [],
        "causal_chains": [],
        "risk_matrix": [],
        "sector_analysis": [],
        "sentiment": [],
        "technicals": [],
        "recommendations": [
            {
                "ticker": "005930",
                "name": "Samsung",
                "market": "KOSPI",
                "direction": "LONG",
                "timeframe": "DAY",
                "entry_price": 70000,
                "target_price": 75000,
                "stop_loss": 68000,
                "sector": "semi",
                "rationale": "good",
                "causal_chain_summary": "x",
                "risk_reward_ratio": 2.5,
                "confidence": "high",
            }
        ],
        "upcoming_events": [],
        "past_performance_commentary": "",
        "disclaimer": "x",
    }
    claude.submit = AsyncMock(return_value=_r(json.dumps(converging_response)))
    codex = MagicMock()
    codex.submit = AsyncMock(
        return_value=_r(
            json.dumps(
                {
                    "agreement_score": 0.95,
                    "dimensions": {
                        "logical_coherence": 1.0,
                        "evidence_quality": 0.9,
                        "remaining_disagreement": "",
                        "sharpening_questions": [],
                    },
                    "false_consensus_detected": False,
                    "false_consensus_reason": None,
                }
            )
        )
    )
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    return LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)


@pytest.mark.asyncio
async def test_daily_debate_runs_and_converges() -> None:
    router = _mock_router_for_convergence()
    graph = await run_debate(
        pipeline="daily",
        router=router,
        memory_store=MagicMock(
            query_metadata=MagicMock(return_value=[]), traverse_tree=MagicMock(return_value=[])
        ),
        context={
            "date": date(2026, 5, 25).isoformat(),
            "market_data": "KOSPI flat",
            "screening": "n/a",
            "retrospective": "x",
            "tickers": ["005930"],
            "regime": "neutral",
        },
        triggered_by="manual",
        max_rounds=3,
    )
    assert graph.state in (DebateState.CONVERGED, DebateState.MAX_ROUNDS_DISSENT)
    assert graph.verdict is not None
    assert graph.verdict.report_content_json["recommendations"][0]["ticker"] == "005930"


@pytest.mark.asyncio
async def test_news_pipeline_runs_without_trader_or_pm() -> None:
    router = _mock_router_for_convergence()
    graph = await run_debate(
        pipeline="news",
        router=router,
        memory_store=MagicMock(
            query_metadata=MagicMock(return_value=[]), traverse_tree=MagicMock(return_value=[])
        ),
        context={
            "date": "2026-05-25",
            "market_data": "",
            "screening": "",
            "retrospective": "",
            "tickers": [],
            "regime": "neutral",
        },
        triggered_by="scheduler",
        max_rounds=2,
    )
    assert graph.pipeline == "news"
    assert graph.verdict is not None
    # News pipeline produces news_items, not recommendations
    assert "news_items" in graph.verdict.report_content_json
