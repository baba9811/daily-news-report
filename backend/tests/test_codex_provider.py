"""Tests for CodexProvider (codex exec --output-last-message wrapper)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from daily_scheduler.domain.ports.llm_provider import LLMError, LLMResult
from daily_scheduler.infrastructure.adapters.llm.codex_provider import CodexProvider
from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import (
    SubprocessNonZeroExit,
    SubprocessResult,
    SubprocessTimeout,
)


@pytest.mark.asyncio
async def test_submit_uses_exec_with_output_last_message() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(
        return_value=SubprocessResult(
            stdout="the answer is 4", stderr="", exit_code=0, duration_ms=42
        )
    )
    provider = CodexProvider(pool=pool, cli_path="/usr/bin/codex")
    result = await provider.submit("What is 2+2?", tools=None, timeout_s=30, model="gpt-5.5")
    assert isinstance(result, LLMResult)
    # No final-message file was created by the mock → falls back to stdout
    assert result.text == "the answer is 4"
    assert result.provider == "codex"
    assert result.model == "gpt-5.5"

    call = pool.run.call_args
    assert call.kwargs["stdin"] == "What is 2+2?"
    cmd = call.args[0]
    assert cmd[0] == "/usr/bin/codex"
    assert cmd[1] == "exec"
    assert "--model" in cmd
    assert "gpt-5.5" in cmd
    assert "--output-last-message" in cmd
    assert cmd[-1] == "-"  # prompt read from stdin


@pytest.mark.asyncio
async def test_empty_output_raises_retryable() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(
        return_value=SubprocessResult(stdout="", stderr="", exit_code=0, duration_ms=1)
    )
    provider = CodexProvider(pool=pool, cli_path="codex")
    with pytest.raises(LLMError) as exc:
        await provider.submit("q", tools=None, timeout_s=10, model="gpt-5.5")
    assert exc.value.provider == "codex"
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_timeout_raises_retryable_llm_error() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(side_effect=SubprocessTimeout("t", cmd_head="codex"))
    provider = CodexProvider(pool=pool, cli_path="codex")
    with pytest.raises(LLMError) as exc:
        await provider.submit("q", tools=None, timeout_s=10, model="gpt-5.5")
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_non_zero_exit_raises_non_retryable() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(side_effect=SubprocessNonZeroExit("exit 2", exit_code=2, stderr="oops"))
    provider = CodexProvider(pool=pool, cli_path="codex")
    with pytest.raises(LLMError) as exc:
        await provider.submit("q", tools=None, timeout_s=10, model="gpt-5.5")
    assert exc.value.retryable is False
