"""Editor and Publisher — sequential nodes for news pipelines."""

from __future__ import annotations

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.entities.debate import Speech
from daily_scheduler.infrastructure.adapters.council.role_registry import tools_for_role
from daily_scheduler.infrastructure.adapters.debate.bull_bear_nodes import _parse_or_empty
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


async def run_editor(*, router: LLMRouter, render_prompt, context) -> Speech:
    """Run the Editor node and return its Speech (news pipeline)."""
    return await _run(Role.EDITOR, router, render_prompt, context)


async def run_publisher(*, router: LLMRouter, render_prompt, context) -> Speech:
    """Run the Publisher node, producing the final news_items payload."""
    return await _run(Role.PUBLISHER, router, render_prompt, context)


async def _run(role, router, render_prompt, context):
    """Submit a single prompt to the resolved provider and wrap the result."""
    provider, binding = router.resolve(role)
    prompt = render_prompt(role, context)
    result = await provider.submit(
        prompt,
        tools=tools_for_role(role) or None,
        timeout_s=binding.timeout_s,
        model=binding.model,
    )
    return Speech(
        agent_role=role,
        text=result.text,
        structured_json=_parse_or_empty(result.text),
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=result.latency_ms,
        cli_command_hash=result.command_hash,
    )
