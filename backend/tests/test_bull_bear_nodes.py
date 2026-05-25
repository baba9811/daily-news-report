"""Tests for Bull and Bear debate nodes."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from daily_scheduler.infrastructure.adapters.debate.bull_bear_nodes import (
    run_bear,
    run_bull,
)

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.ports.llm_provider import LLMResult
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


def _stub_result(text: str) -> LLMResult:
    return LLMResult(
        text=text,
        model="opus",
        provider="claude-code",
        tokens_in=0,
        tokens_out=0,
        latency_ms=10,
        command_hash="abc",
    )


@pytest.mark.asyncio
async def test_bull_returns_speech_with_structured() -> None:
    claude = MagicMock()
    claude.submit = AsyncMock(
        return_value=_stub_result(
            json.dumps({"direction": "BUY", "top_tickers": ["005930"], "risk_band": "MID"})
        )
    )
    codex = MagicMock()
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

    speech = await run_bull(
        router=router,
        render_prompt=lambda role, ctx: "p",
        context={},
    )
    assert speech.agent_role is Role.BULL
    assert speech.structured_json["direction"] == "BUY"


@pytest.mark.asyncio
async def test_bear_returns_speech() -> None:
    claude = MagicMock()
    claude.submit = AsyncMock(
        return_value=_stub_result(
            json.dumps({"direction": "SELL", "top_tickers": ["000660"], "risk_band": "HIGH"})
        )
    )
    codex = MagicMock()
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

    speech = await run_bear(
        router=router,
        render_prompt=lambda role, ctx: "p",
        context={},
    )
    assert speech.agent_role is Role.BEAR
    assert speech.structured_json["direction"] == "SELL"
