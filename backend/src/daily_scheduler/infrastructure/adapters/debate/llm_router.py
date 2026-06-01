"""LLMRouter — resolves Role → (LLMProviderPort, BackendBinding) respecting overrides."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass

from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role
from daily_scheduler.domain.ports.agent_binding_repo import AgentBindingRepositoryPort
from daily_scheduler.domain.ports.llm_provider import LLMProviderPort
from daily_scheduler.infrastructure.adapters.council.role_registry import (
    default_binding_for,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LLMRouter:
    """Resolve a Role to the correct LLMProviderPort + BackendBinding.

    Looks up an override in the AgentBindingRepository first; if none, falls
    back to the default binding registered for the role.

    If the resolved provider's CLI binary is not on PATH, falls back to the
    other provider with a logged warning. This keeps debates running even
    when ``codex`` (or ``claude``) is missing from a constrained launchd PATH.
    """

    claude_code: LLMProviderPort
    codex: LLMProviderPort
    binding_repo: AgentBindingRepositoryPort

    def resolve(self, role: Role) -> tuple[LLMProviderPort, BackendBinding]:
        """Return (provider, binding) for the role, honoring any override."""
        binding = self.binding_repo.get(role) or default_binding_for(role)
        if binding.provider is Provider.CODEX:
            if _cli_available("codex"):
                return self.codex, binding
            if _cli_available("claude"):
                logger.warning(
                    "codex CLI not on PATH for role %s — falling back to claude-code (sonnet)",
                    role.value,
                )
                # Degraded path (cross-model diversity already lost): use sonnet,
                # not opus — these codex roles are deliberation/decision lenses,
                # not the final synthesis.
                fallback = BackendBinding(
                    provider=Provider.CLAUDE_CODE,
                    model="sonnet",
                    system_prompt_override=binding.system_prompt_override,
                    timeout_s=binding.timeout_s,
                )
                return self.claude_code, fallback
            logger.error(
                "neither codex nor claude CLI on PATH for role %s — using codex anyway "
                "(will fail at call time)",
                role.value,
            )
            return self.codex, binding
        return self.claude_code, binding


def _cli_available(name: str) -> bool:
    """Return True if `name` is resolvable via shutil.which."""
    return shutil.which(name) is not None
