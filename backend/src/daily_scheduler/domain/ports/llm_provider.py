"""Port for LLM providers (subscription-based CLIs).

Implementations: ClaudeCodeProvider (claude -p), CodexProvider (codex exec).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Result of a single LLM submission."""

    text: str
    model: str
    provider: str  # "claude-code" | "codex"
    tokens_in: int
    tokens_out: int
    latency_ms: int
    command_hash: str  # first 16 hex chars of SHA-256 of the command


class LLMError(Exception):
    """Raised when an LLM provider call fails after retries."""

    def __init__(self, message: str, *, provider: str, retryable: bool) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


class LLMProviderPort(Protocol):
    """Abstract LLM provider — subprocess CLI (claude-code or codex)."""

    async def submit(
        self,
        prompt: str,
        *,
        tools: list[str] | None,
        timeout_s: int,
        model: str,
    ) -> LLMResult:
        """Submit a prompt and return the response.

        Raises LLMError on irrecoverable failure (after internal retries).
        """
        ...
