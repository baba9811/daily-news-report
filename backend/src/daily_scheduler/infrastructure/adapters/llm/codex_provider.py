"""Codex CLI provider — wraps `codex exec` (ChatGPT subscription) via SubprocessPool.

`codex exec` does not support a JSON envelope flag; instead we use
``-o/--output-last-message <FILE>`` to capture only the agent's final message,
avoiding the interactive header/log noise that `codex exec` prints to stdout.
The prompt is passed on stdin (``-`` argument). Authentication is the user's
ChatGPT subscription — no API key.
"""

from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path

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
    """LLM provider backed by `codex exec`, capturing the final message."""

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
        # Capture only the final agent message in a temp file.
        with tempfile.NamedTemporaryFile(
            mode="r", suffix=".txt", prefix="codex_out_", delete=False
        ) as handle:
            out_path = handle.name

        cmd = [
            self._cli_path,
            "exec",
            "--model",
            model,
            "--output-last-message",
            out_path,
            "-",  # read prompt from stdin
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
            text = self._read_output(out_path, fallback_stdout=result.stdout)
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
        finally:
            Path(out_path).unlink(missing_ok=True)

        if not text.strip():
            raise LLMError(
                "codex produced an empty final message",
                provider="codex",
                retryable=True,
            )

        return LLMResult(
            text=text,
            model=model,
            provider="codex",
            tokens_in=0,
            tokens_out=0,
            latency_ms=result.duration_ms,
            command_hash=cmd_hash,
        )

    @staticmethod
    def _read_output(out_path: str, *, fallback_stdout: str) -> str:
        """Read the captured final message; fall back to stdout if the file is empty."""
        try:
            content = Path(out_path).read_text(encoding="utf-8").strip()
        except OSError:
            content = ""
        return content or fallback_stdout
