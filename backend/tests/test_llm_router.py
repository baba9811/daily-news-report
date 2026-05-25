"""Tests for LLM Router — resolves Role → LLMProviderPort respecting overrides."""

from __future__ import annotations

from unittest.mock import MagicMock

from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role


def test_router_uses_default_when_no_override() -> None:
    claude = MagicMock(name="claude_code")
    codex = MagicMock(name="codex")
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=None)
    router = LLMRouter(
        claude_code=claude,
        codex=codex,
        binding_repo=binding_repo,
    )
    provider, binding = router.resolve(Role.JUDGE)
    assert provider is codex
    assert binding.provider is Provider.CODEX


def test_router_uses_override_when_present() -> None:
    claude = MagicMock()
    codex = MagicMock()
    override = BackendBinding(provider=Provider.CODEX, model="gpt-5-codex", timeout_s=120)
    binding_repo = MagicMock()
    binding_repo.get = MagicMock(return_value=override)
    router = LLMRouter(
        claude_code=claude,
        codex=codex,
        binding_repo=binding_repo,
    )
    provider, binding = router.resolve(Role.BULL)
    assert provider is codex  # override flipped to codex
    assert binding.timeout_s == 120
