"""Tests for CodexProvider (codex exec subprocess wrapper)."""

from __future__ import annotations

import json
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
async def test_submit_passes_prompt_via_stdin() -> None:
    envelope = {"output": "the answer is 4", "tokens_in": 12, "tokens_out": 5}
    pool = MagicMock()
    pool.run = AsyncMock(
        return_value=SubprocessResult(
            stdout=json.dumps(envelope), stderr="", exit_code=0, duration_ms=42
        )
    )
    provider = CodexProvider(pool=pool, cli_path="/usr/bin/codex")
    result = await provider.submit(
        "What is 2+2?",
        tools=None,
        timeout_s=30,
        model="gpt-5-codex",
    )
    assert isinstance(result, LLMResult)
    assert result.text == "the answer is 4"
    assert result.provider == "codex"
    assert result.tokens_in == 12
    assert result.tokens_out == 5
    call = pool.run.call_args
    assert call.kwargs["stdin"] == "What is 2+2?"
    cmd = call.args[0]
    assert cmd[0] == "/usr/bin/codex"
    assert cmd[1] == "exec"
    assert "--model" in cmd
    assert "gpt-5-codex" in cmd
    assert "--output-format" in cmd
    assert "json" in cmd


@pytest.mark.asyncio
async def test_invalid_json_output_raises_llm_error_non_retryable() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(
        return_value=SubprocessResult(stdout="not json {{", stderr="", exit_code=0, duration_ms=1)
    )
    provider = CodexProvider(pool=pool, cli_path="codex")
    with pytest.raises(LLMError) as exc:
        await provider.submit("q", tools=None, timeout_s=10, model="gpt-5-codex")
    assert exc.value.retryable is False


@pytest.mark.asyncio
async def test_envelope_without_output_field_raises() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(
        return_value=SubprocessResult(
            stdout='{"foo": "bar"}', stderr="", exit_code=0, duration_ms=1
        )
    )
    provider = CodexProvider(pool=pool, cli_path="codex")
    with pytest.raises(LLMError) as exc:
        await provider.submit("q", tools=None, timeout_s=10, model="gpt-5-codex")
    assert exc.value.retryable is False


@pytest.mark.asyncio
async def test_timeout_raises_retryable_llm_error() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(side_effect=SubprocessTimeout("t", cmd_head="codex"))
    provider = CodexProvider(pool=pool, cli_path="codex")
    with pytest.raises(LLMError) as exc:
        await provider.submit("q", tools=None, timeout_s=10, model="gpt-5-codex")
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_non_zero_exit_raises_non_retryable() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(side_effect=SubprocessNonZeroExit("exit 2", exit_code=2, stderr="oops"))
    provider = CodexProvider(pool=pool, cli_path="codex")
    with pytest.raises(LLMError) as exc:
        await provider.submit("q", tools=None, timeout_s=10, model="gpt-5-codex")
    assert exc.value.retryable is False
