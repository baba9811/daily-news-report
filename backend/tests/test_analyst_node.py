"""Tests for the parallel analyst node."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.ports.llm_provider import LLMResult
from daily_scheduler.infrastructure.adapters.debate.analyst_node import (
    run_analyst_pool,
)


def _result_for(role: str) -> LLMResult:
    return LLMResult(
        text=json.dumps({"role": role, "top_picks": ["005930"]}),
        model="opus",
        provider="claude-code",
        tokens_in=0,
        tokens_out=0,
        latency_ms=10,
        command_hash="abc",
    )


@pytest.mark.asyncio
async def test_run_analyst_pool_calls_each_role_in_parallel() -> None:
    claude = MagicMock()
    claude.submit = AsyncMock(side_effect=lambda prompt, **kw: _result_for(prompt[:20]))
    codex = MagicMock()
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

    router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

    analyst_roles = [
        Role.KR_FUNDAMENTALS,
        Role.US_FUNDAMENTALS,
        Role.KR_TECHNICAL,
        Role.US_TECHNICAL,
        Role.NEWS_SENT,
    ]
    results = await run_analyst_pool(
        analyst_roles=analyst_roles,
        router=router,
        render_prompt=lambda role, ctx: f"prompt for {role.value}",
        context={"date": "2026-05-25"},
    )
    assert len(results) == 5
    assert claude.submit.call_count == 5
    for r in results:
        assert "role" in r
        assert "top_picks" in r


@pytest.mark.asyncio
async def test_analyst_non_json_response_kept_as_text() -> None:
    claude = MagicMock()
    claude.submit = AsyncMock(
        return_value=LLMResult(
            text="not json",
            model="opus",
            provider="claude-code",
            tokens_in=0,
            tokens_out=0,
            latency_ms=10,
            command_hash="abc",
        )
    )
    codex = MagicMock()
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

    router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

    results = await run_analyst_pool(
        analyst_roles=[Role.KR_FUNDAMENTALS],
        router=router,
        render_prompt=lambda r, c: "p",
        context={},
    )
    assert len(results) == 1
    assert results[0]["raw_text"] == "not json"
    assert results[0]["role"] == "kr_fundamentals"
