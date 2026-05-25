"""Codex CLI provider — wraps `codex exec --output-format json` via SubprocessPool."""

from __future__ import annotations

import hashlib
import json
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


class CodexProvider(LLMProviderPort):
    """LLM provider backed by `codex exec` in JSON output mode."""

    def __init__(self, pool: SubprocessPool, cli_path: str) -> None:
        self._pool = pool
        self._cli_path = cli_path

    async def submit(
        self,
        prompt: str,
        *,
        tools: list[str] | None,  # noqa: ARG002  (codex tool flags reserved)
        timeout_s: int,
        model: str,
    ) -> LLMResult:
        cmd = [
            self._cli_path,
            "exec",
            "--model",
            model,
            "--output-format",
            "json",
        ]
        cmd_hash = hashlib.sha256(" ".join(cmd + [prompt[:64]]).encode()).hexdigest()[:16]
        logger.info("codex submit model=%s timeout=%ds cmd_hash=%s", model, timeout_s, cmd_hash)

        try:
            result = await self._pool.run(
                cmd,
                stdin=prompt,
                timeout_s=timeout_s,
                retries=LLM_RETRY_COUNT,
            )
        except SubprocessTimeout as e:
            raise LLMError(
                f"codex timed out after {timeout_s}s",
                provider="codex",
                retryable=True,
            ) from e
        except SubprocessNonZeroExit as e:
            raise LLMError(
                f"codex exited {e.exit_code}: {e.stderr[:200]}",
                provider="codex",
                retryable=False,
            ) from e

        try:
            envelope = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise LLMError(
                f"codex returned invalid JSON: {result.stdout[:200]}",
                provider="codex",
                retryable=False,
            ) from e

        if not isinstance(envelope, dict) or "output" not in envelope:
            raise LLMError(
                f"codex envelope missing 'output' field: {str(envelope)[:200]}",
                provider="codex",
                retryable=False,
            )

        return LLMResult(
            text=str(envelope["output"]),
            model=model,
            provider="codex",
            tokens_in=int(envelope.get("tokens_in", 0)),
            tokens_out=int(envelope.get("tokens_out", 0)),
            latency_ms=result.duration_ms,
            command_hash=cmd_hash,
        )
