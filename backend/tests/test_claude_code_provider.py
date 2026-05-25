"""Tests for ClaudeCodeProvider (claude -p subprocess wrapper)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from daily_scheduler.infrastructure.adapters.llm.claude_code_provider import (
    ClaudeCodeProvider,
)

from daily_scheduler.domain.ports.llm_provider import LLMError, LLMResult
from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import (
    SubprocessNonZeroExit,
    SubprocessResult,
    SubprocessTimeout,
)


def _ok_result(stdout: str = "answer") -> SubprocessResult:
    return SubprocessResult(stdout=stdout, stderr="", exit_code=0, duration_ms=100)


@pytest.mark.asyncio
async def test_submit_builds_claude_command_correctly() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(return_value=_ok_result())
    provider = ClaudeCodeProvider(pool=pool, cli_path="/usr/bin/claude")
    result = await provider.submit(
        "What is 2+2?",
        tools=["WebSearch", "WebFetch"],
        timeout_s=60,
        model="opus",
    )
    assert isinstance(result, LLMResult)
    assert result.text == "answer"
    assert result.provider == "claude-code"
    assert result.model == "opus"
    cmd = pool.run.call_args.args[0]
    assert cmd[0] == "/usr/bin/claude"
    assert "-p" in cmd
    assert cmd[cmd.index("-p") + 1] == "What is 2+2?"
    assert "--model" in cmd and cmd[cmd.index("--model") + 1] == "opus"
    assert "--output-format" in cmd and cmd[cmd.index("--output-format") + 1] == "text"
    assert "--permission-mode" in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "bypassPermissions"
    assert "--tools" in cmd and cmd[cmd.index("--tools") + 1] == "WebSearch,WebFetch"
    assert "--disallowed-tools" in cmd


@pytest.mark.asyncio
async def test_submit_without_tools_omits_tools_flag() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(return_value=_ok_result("x"))
    provider = ClaudeCodeProvider(pool=pool, cli_path="claude")
    await provider.submit("hi", tools=None, timeout_s=60, model="sonnet")
    cmd = pool.run.call_args.args[0]
    assert "--tools" not in cmd
    assert "--disallowed-tools" in cmd


@pytest.mark.asyncio
async def test_submit_timeout_raises_llm_error_retryable() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(side_effect=SubprocessTimeout("timeout", cmd_head="claude -p"))
    provider = ClaudeCodeProvider(pool=pool, cli_path="claude")
    with pytest.raises(LLMError) as exc:
        await provider.submit("q", tools=None, timeout_s=10, model="opus")
    assert exc.value.provider == "claude-code"
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_submit_non_zero_raises_llm_error_non_retryable() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(side_effect=SubprocessNonZeroExit("exit 1", exit_code=1, stderr="boom"))
    provider = ClaudeCodeProvider(pool=pool, cli_path="claude")
    with pytest.raises(LLMError) as exc:
        await provider.submit("q", tools=None, timeout_s=10, model="opus")
    assert exc.value.provider == "claude-code"
    assert exc.value.retryable is False


@pytest.mark.asyncio
async def test_command_hash_is_16_hex_chars() -> None:
    pool = MagicMock()
    pool.run = AsyncMock(return_value=_ok_result("x"))
    provider = ClaudeCodeProvider(pool=pool, cli_path="claude")
    result = await provider.submit("q", tools=None, timeout_s=10, model="opus")
    assert len(result.command_hash) == 16
    assert all(c in "0123456789abcdef" for c in result.command_hash)
