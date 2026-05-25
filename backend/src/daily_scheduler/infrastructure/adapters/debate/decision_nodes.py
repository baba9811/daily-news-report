"""Trader, RiskMgmt, PortfolioMgr — sequential decision nodes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.entities.debate import Speech
from daily_scheduler.infrastructure.adapters.debate.bull_bear_nodes import _parse_or_empty
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


async def run_trader(*, router: LLMRouter, render_prompt, context) -> Speech:
    return await _run(Role.TRADER, router, render_prompt, context)


async def run_risk_mgmt(*, router: LLMRouter, render_prompt, context) -> Speech:
    return await _run(Role.RISK_MGMT, router, render_prompt, context)


async def run_pm(*, router: LLMRouter, render_prompt, context) -> Speech:
    return await _run(Role.PORTFOLIO_MGR, router, render_prompt, context)


async def _run(
    role: Role,
    router: LLMRouter,
    render_prompt: Callable[[Role, dict[str, Any]], str],
    context: dict[str, Any],
) -> Speech:
    provider, binding = router.resolve(role)
    prompt = render_prompt(role, context)
    result = await provider.submit(
        prompt,
        tools=None,
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
