"""CouncilNewsProvider — implements NewsProviderPort for the 4 pipelines."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from daily_scheduler.domain.ports.llm_provider import LLMResult
from daily_scheduler.infrastructure.adapters.claude.parser import parse_report_content
from daily_scheduler.infrastructure.adapters.council.council_news_provider import (
    CouncilNewsProvider,
)
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


def _full_pm_payload() -> dict:
    return {
        "report_date": "2026-05-25",
        "market_summary": "ok",
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
                "rationale": "x",
                "causal_chain_summary": "y",
                "risk_reward_ratio": 2.5,
                "confidence": "high",
            }
        ],
        "upcoming_events": [],
        "past_performance_commentary": "",
        "disclaimer": "x",
    }


def _convergence_router() -> LLMRouter:
    claude = MagicMock()
    claude.submit = AsyncMock(
        return_value=LLMResult(
            text=json.dumps(_full_pm_payload()),
            model="opus",
            provider="claude-code",
            tokens_in=0,
            tokens_out=0,
            latency_ms=1,
            command_hash="a",
        )
    )
    codex = MagicMock()
    codex.submit = AsyncMock(
        return_value=LLMResult(
            text=json.dumps(
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
            ),
            model="gpt-5-codex",
            provider="codex",
            tokens_in=0,
            tokens_out=0,
            latency_ms=1,
            command_hash="b",
        )
    )
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    return LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)


def test_generate_daily_report_returns_text_and_elapsed() -> None:
    memory = MagicMock(
        query_metadata=MagicMock(return_value=[]),
        traverse_tree=MagicMock(return_value=[]),
    )
    provider = CouncilNewsProvider(router=_convergence_router(), memory_store=memory)
    # Sync NewsProviderPort interface — invoked from CLI/scheduler.
    text, elapsed = provider.generate_daily_report(
        report_date=date(2026, 5, 25),
        retrospective_context="x",
        weekly_lessons="",
        market_data="m",
        screening_data="s",
    )
    assert isinstance(text, str)
    assert elapsed >= 0
    parsed = parse_report_content(text)
    assert parsed is not None
    assert parsed.report_date == "2026-05-25"


@pytest.mark.asyncio
async def test_sync_wrapper_methods_present() -> None:
    """Existing pipeline code calls these via synchronous interface."""
    memory = MagicMock(
        query_metadata=MagicMock(return_value=[]),
        traverse_tree=MagicMock(return_value=[]),
    )
    provider = CouncilNewsProvider(router=_convergence_router(), memory_store=memory)
    # All four methods exist with the expected sync signature
    assert callable(provider.generate_daily_report)
    assert callable(provider.generate_weekly_report)
    assert callable(provider.generate_news_briefing)
    assert callable(provider.generate_global_news_briefing)


def test_provider_implements_news_provider_port() -> None:
    """Quick structural check — the four method names exist."""
    memory = MagicMock()
    provider = CouncilNewsProvider(router=MagicMock(), memory_store=memory)
    for m in (
        "generate_daily_report",
        "generate_weekly_report",
        "generate_news_briefing",
        "generate_global_news_briefing",
    ):
        assert hasattr(provider, m)


def test_provider_persists_debate_via_repo_when_provided() -> None:
    """When a DebateRepository is provided, finished graphs are saved."""
    memory = MagicMock(
        query_metadata=MagicMock(return_value=[]),
        traverse_tree=MagicMock(return_value=[]),
    )
    debate_repo = MagicMock()
    debate_repo.save = MagicMock()

    provider = CouncilNewsProvider(
        router=_convergence_router(),
        memory_store=memory,
        debate_repo=debate_repo,
    )
    provider.generate_daily_report(
        report_date=date(2026, 5, 25),
        retrospective_context="x",
    )
    debate_repo.save.assert_called_once()


def test_provider_swallows_debate_repo_save_errors() -> None:
    """Failures inside debate_repo.save must not break the report."""
    memory = MagicMock(
        query_metadata=MagicMock(return_value=[]),
        traverse_tree=MagicMock(return_value=[]),
    )
    debate_repo = MagicMock()
    debate_repo.save = MagicMock(side_effect=RuntimeError("db down"))

    provider = CouncilNewsProvider(
        router=_convergence_router(),
        memory_store=memory,
        debate_repo=debate_repo,
    )
    text, elapsed = provider.generate_daily_report(
        report_date=date(2026, 5, 25),
        retrospective_context="x",
    )
    assert isinstance(text, str)
    assert elapsed >= 0
    parsed = parse_report_content(text)
    assert parsed is not None
