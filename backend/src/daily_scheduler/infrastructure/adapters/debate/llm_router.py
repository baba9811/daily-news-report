"""LLMRouter — resolves Role → (LLMProviderPort, BackendBinding) respecting overrides."""

from __future__ import annotations

from dataclasses import dataclass

from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role
from daily_scheduler.domain.ports.agent_binding_repo import AgentBindingRepositoryPort
from daily_scheduler.domain.ports.llm_provider import LLMProviderPort
from daily_scheduler.infrastructure.adapters.council.role_registry import (
    default_binding_for,
)


@dataclass(frozen=True, slots=True)
class LLMRouter:
    """Resolve a Role to the correct LLMProviderPort + BackendBinding.

    Looks up an override in the AgentBindingRepository first; if none, falls
    back to the default binding registered for the role.
    """

    claude_code: LLMProviderPort
    codex: LLMProviderPort
    binding_repo: AgentBindingRepositoryPort

    def resolve(self, role: Role) -> tuple[LLMProviderPort, BackendBinding]:
        """Return (provider, binding) for the role, honoring any override."""
        binding = self.binding_repo.get(role) or default_binding_for(role)
        if binding.provider is Provider.CODEX:
            return self.codex, binding
        return self.claude_code, binding
