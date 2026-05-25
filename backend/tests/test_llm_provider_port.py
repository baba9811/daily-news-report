"""Tests for LLMProviderPort and LLMResult."""

from __future__ import annotations

from daily_scheduler.domain.ports.llm_provider import (
    LLMError,
    LLMProviderPort,
    LLMResult,
)


def test_llm_result_holds_text_and_metadata() -> None:
    result = LLMResult(
        text="hello",
        model="opus",
        provider="claude-code",
        tokens_in=10,
        tokens_out=2,
        latency_ms=1234,
        command_hash="deadbeefdeadbeef",
    )
    assert result.text == "hello"
    assert result.model == "opus"
    assert result.provider == "claude-code"
    assert result.tokens_in == 10
    assert result.tokens_out == 2
    assert result.latency_ms == 1234
    assert len(result.command_hash) == 16


def test_llm_error_carries_cause() -> None:
    err = LLMError("timeout after 30s", provider="codex", retryable=True)
    assert str(err) == "timeout after 30s"
    assert err.provider == "codex"
    assert err.retryable is True


def test_llm_provider_port_is_protocol() -> None:
    assert hasattr(LLMProviderPort, "submit")
