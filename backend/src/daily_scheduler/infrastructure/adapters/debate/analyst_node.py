"""Parallel analyst pool — runs N analyst roles concurrently via the LLM pool."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.infrastructure.adapters.council.role_registry import (
    tools_for_role,
)
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

logger = logging.getLogger(__name__)


async def run_analyst_pool(
    *,
    analyst_roles: list[Role],
    router: LLMRouter,
    render_prompt: Callable[[Role, dict[str, Any]], str],
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run all analyst roles in parallel. Returns list of structured dicts."""

    async def _one(role: Role) -> dict[str, Any]:
        provider, binding = router.resolve(role)
        prompt = render_prompt(role, context)
        tools = tools_for_role(role)
        try:
            result = await provider.submit(
                prompt,
                tools=tools or None,
                timeout_s=binding.timeout_s,
                model=binding.model,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("analyst %s failed: %s", role.value, e)
            return {"role": role.value, "error": str(e), "raw_text": ""}

        structured = _try_parse_json(result.text)
        out: dict[str, Any] = {
            "role": role.value,
            "provider": result.provider,
            "model": result.model,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "latency_ms": result.latency_ms,
            "cli_command_hash": result.command_hash,
        }
        if structured is None:
            out["raw_text"] = result.text
        else:
            out["raw_text"] = result.text
            out.update(structured)
        return out

    return await asyncio.gather(*(_one(r) for r in analyst_roles))


def _try_parse_json(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    # Try entire blob
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    # Try ```json block
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
    return None
