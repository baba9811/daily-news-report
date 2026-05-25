"""Tests for Editor and Publisher nodes (news pipelines)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from daily_scheduler.infrastructure.adapters.debate.editor_publisher_nodes import (
    run_editor,
    run_publisher,
)

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.ports.llm_provider import LLMResult
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


def _router(text: str) -> LLMRouter:
    claude = MagicMock()
    claude.submit = AsyncMock(
        return_value=LLMResult(
            text=text,
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
    return LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)


@pytest.mark.asyncio
async def test_editor_returns_speech() -> None:
    payload = json.dumps({"news_items": [{"headline": "x", "summary": "y"}]})
    s = await run_editor(router=_router(payload), render_prompt=lambda r, c: "p", context={})
    assert s.agent_role is Role.EDITOR


@pytest.mark.asyncio
async def test_publisher_returns_speech() -> None:
    payload = json.dumps({"approve": True, "news_items": [{"headline": "x"}]})
    s = await run_publisher(router=_router(payload), render_prompt=lambda r, c: "p", context={})
    assert s.agent_role is Role.PUBLISHER
