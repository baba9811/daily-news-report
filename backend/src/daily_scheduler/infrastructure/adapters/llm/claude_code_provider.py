"""Claude Code CLI provider — wraps `claude -p` invocations via SubprocessPool.

Authentication is via the user's Claude Code subscription (OAuth in OS keychain).
No API key required.
"""

from __future__ import annotations

import hashlib
import logging

from daily_scheduler.constants import LLM_RETRY_COUNT
from daily_scheduler.domain.ports.llm_provider import (
    LLMError,
    LLMProviderPort,
    LLMResult,
)
from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import (
    SubprocessNonZeroExit,
    SubprocessPool,
    SubprocessTimeout,
)

logger = logging.getLogger(__name__)

_DISALLOWED_TOOLS = "Write,Edit,Bash,ExitPlanMode,EnterPlanMode,TodoWrite"


class ClaudeCodeProvider(LLMProviderPort):
    """LLM provider backed by the `claude` CLI in print mode."""

    def __init__(self, pool: SubprocessPool, cli_path: str) -> None:
        self._pool = pool
        self._cli_path = cli_path

    async def submit(
        self,
        prompt: str,
        *,
        tools: list[str] | None,
        timeout_s: int,
        model: str,
    ) -> LLMResult:
        cmd = [
            self._cli_path,
            "-p",
            prompt,
            "--model",
            model,
            "--output-format",
            "text",
            "--permission-mode",
            "bypassPermissions",
            "--disallowed-tools",
            _DISALLOWED_TOOLS,
        ]
        if tools:
            cmd.extend(["--tools", ",".join(tools)])

        cmd_hash = hashlib.sha256(" ".join(cmd).encode()).hexdigest()[:16]
        logger.info(
            "claude-code submit model=%s tools=%s timeout=%ds cmd_hash=%s",
            model,
            tools,
            timeout_s,
            cmd_hash,
        )

        try:
            result = await self._pool.run(
                cmd,
                stdin="",
                timeout_s=timeout_s,
                retries=LLM_RETRY_COUNT,
            )
        except SubprocessTimeout as e:
            raise LLMError(
                f"claude-code timed out after {timeout_s}s",
                provider="claude-code",
                retryable=True,
            ) from e
        except SubprocessNonZeroExit as e:
            raise LLMError(
                f"claude-code exited {e.exit_code}: {e.stderr[:200]}",
                provider="claude-code",
                retryable=False,
            ) from e

        return LLMResult(
            text=result.stdout,
            model=model,
            provider="claude-code",
            tokens_in=0,
            tokens_out=0,
            latency_ms=result.duration_ms,
            command_hash=cmd_hash,
        )
