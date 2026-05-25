"""Bull and Bear debate nodes."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.entities.debate import Speech
from daily_scheduler.infrastructure.adapters.council.role_registry import (
    tools_for_role,
)
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


async def run_bull(
    *,
    router: LLMRouter,
    render_prompt: Callable[[Role, dict[str, Any]], str],
    context: dict[str, Any],
) -> Speech:
    """Run the Bull debater for the current round and return its Speech."""
    return await _run_debater(
        Role.BULL,
        router=router,
        render_prompt=render_prompt,
        context=context,
    )


async def run_bear(
    *,
    router: LLMRouter,
    render_prompt: Callable[[Role, dict[str, Any]], str],
    context: dict[str, Any],
) -> Speech:
    """Run the Bear debater for the current round and return its Speech."""
    return await _run_debater(
        Role.BEAR,
        router=router,
        render_prompt=render_prompt,
        context=context,
    )


async def _run_debater(
    role: Role,
    *,
    router: LLMRouter,
    render_prompt: Callable[[Role, dict[str, Any]], str],
    context: dict[str, Any],
) -> Speech:
    provider, binding = router.resolve(role)
    prompt = render_prompt(role, context)
    result = await provider.submit(
        prompt,
        tools=tools_for_role(role) or None,
        timeout_s=binding.timeout_s,
        model=binding.model,
    )
    structured = _parse_or_empty(result.text)
    return Speech(
        agent_role=role,
        text=result.text,
        structured_json=structured,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=result.latency_ms,
        cli_command_hash=result.command_hash,
    )


def _parse_or_empty(text: str) -> dict[str, Any]:
    """Best-effort JSON parse — returns a dict or {'raw_text': text} on failure.

    Reused by the Judge node (Task 10) to parse Bull/Bear structured output.
    """
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    if "```json" in stripped:
        start = stripped.find("```json") + len("```json")
        end = stripped.find("```", start)
        if end != -1:
            try:
                parsed = json.loads(stripped[start:end].strip())
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
    return {"raw_text": text}
