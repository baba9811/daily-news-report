"""Tests for LLM Router — resolves Role → LLMProviderPort respecting overrides."""

from __future__ import annotations

from unittest.mock import MagicMock

from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role
from daily_scheduler.infrastructure.adapters.debate import llm_router as llm_router_mod
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


def _router() -> tuple[LLMRouter, MagicMock, MagicMock, MagicMock]:
    claude = MagicMock(name="claude_code")
    codex = MagicMock(name="codex")
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    return (
        LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo),
        claude,
        codex,
        binding_repo,
    )


def test_judge_default_routes_to_claude_code() -> None:
    # JUDGE now defaults to claude-code (codex requires explicit ChatGPT config).
    router, claude, _codex, _repo = _router()
    provider, binding = router.resolve(Role.JUDGE)
    assert provider is claude
    assert binding.provider is Provider.CLAUDE_CODE


def test_codex_override_routes_to_codex_when_available(monkeypatch) -> None:
    monkeypatch.setattr(llm_router_mod, "_cli_available", lambda name: True)
    router, _claude, codex, repo = _router()
    repo.get = MagicMock(
        return_value=BackendBinding(provider=Provider.CODEX, model="gpt-5.5", timeout_s=120)
    )
    provider, binding = router.resolve(Role.BULL)
    assert provider is codex
    assert binding.provider is Provider.CODEX
    assert binding.timeout_s == 120


def test_codex_override_falls_back_to_claude_when_codex_missing(monkeypatch) -> None:
    # codex absent from PATH, claude present → graceful fallback.
    monkeypatch.setattr(llm_router_mod, "_cli_available", lambda name: name != "codex")
    router, claude, _codex, repo = _router()
    repo.get = MagicMock(
        return_value=BackendBinding(provider=Provider.CODEX, model="gpt-5.5", timeout_s=120)
    )
    provider, binding = router.resolve(Role.BULL)
    assert provider is claude
    assert binding.provider is Provider.CLAUDE_CODE


def test_claude_code_role_routes_to_claude() -> None:
    router, claude, _codex, _repo = _router()
    provider, binding = router.resolve(Role.BULL)
    assert provider is claude
    assert binding.provider is Provider.CLAUDE_CODE
