"""Tests for Trader / RiskMgmt / PortfolioMgr nodes."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.ports.llm_provider import LLMResult
from daily_scheduler.infrastructure.adapters.debate.decision_nodes import (
    run_pm,
    run_risk_mgmt,
    run_trader,
)
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


def _r(text: str) -> LLMResult:
    return LLMResult(
        text=text,
        model="opus",
        provider="claude-code",
        tokens_in=0,
        tokens_out=0,
        latency_ms=10,
        command_hash="abc",
    )


def _router(claude_text: str) -> LLMRouter:
    # Mock BOTH providers identically so the test is agnostic to which backend
    # a role resolves to (Trader/Risk default to codex/GPT-5.5; PM to claude).
    submit = AsyncMock(return_value=_r(claude_text))
    claude = MagicMock()
    claude.submit = submit
    codex = MagicMock()
    codex.submit = submit
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    return LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)


@pytest.mark.asyncio
async def test_trader_emits_speech_with_proposals() -> None:
    router = _router(json.dumps({"proposals": [{"ticker": "005930", "size_pct": 5}]}))
    s = await run_trader(router=router, render_prompt=lambda r, c: "p", context={})
    assert s.agent_role is Role.TRADER
    assert s.structured_json["proposals"][0]["ticker"] == "005930"


@pytest.mark.asyncio
async def test_risk_mgmt_returns_decision_speech() -> None:
    router = _router(json.dumps({"decision": "APPROVE", "modifications": []}))
    s = await run_risk_mgmt(router=router, render_prompt=lambda r, c: "p", context={})
    assert s.agent_role is Role.RISK_MGMT


@pytest.mark.asyncio
async def test_pm_emits_final_recommendations() -> None:
    payload = {
        "market_summary": "summary text",
        "recommendations": [
            {
                "ticker": "005930",
                "direction": "LONG",
                "timeframe": "DAY",
                "entry_price": 70000,
                "target_price": 75000,
                "stop_loss": 68000,
            }
        ],
    }
    router = _router(json.dumps(payload))
    s = await run_pm(router=router, render_prompt=lambda r, c: "p", context={})
    assert s.agent_role is Role.PORTFOLIO_MGR
    assert s.structured_json["recommendations"][0]["ticker"] == "005930"
