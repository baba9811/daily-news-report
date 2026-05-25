"""Debate orchestrator — runs the agent graph for a single pipeline invocation."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ulid import ULID

from daily_scheduler.constants import (
    JUDGE_LLM_THRESHOLD,
    JUDGE_RULE_THRESHOLD,
    MAX_DEBATE_ROUNDS_DAILY,
    MAX_DEBATE_ROUNDS_NEWS,
    MAX_DEBATE_ROUNDS_WEEKLY,
)
from daily_scheduler.domain.entities.agent import Role, roles_for_pipeline
from daily_scheduler.domain.entities.debate import (
    ConsensusScore,
    DebateGraph,
    DebateState,
    Round,
    Speech,
    Verdict,
)
from daily_scheduler.domain.ports.memory_store import MemoryStorePort
from daily_scheduler.infrastructure.adapters.council.prompt_templates import (
    render_agent_prompt,
)
from daily_scheduler.infrastructure.adapters.debate.analyst_node import run_analyst_pool
from daily_scheduler.infrastructure.adapters.debate.bull_bear_nodes import (
    run_bear,
    run_bull,
)
from daily_scheduler.infrastructure.adapters.debate.decision_nodes import (
    run_pm,
    run_risk_mgmt,
    run_trader,
)
from daily_scheduler.infrastructure.adapters.debate.editor_publisher_nodes import (
    run_editor,
    run_publisher,
)
from daily_scheduler.infrastructure.adapters.debate.graph_builder import (
    is_news_pipeline,
    is_weekly_pipeline,
)
from daily_scheduler.infrastructure.adapters.debate.judge_node import run_judge
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

logger = logging.getLogger(__name__)


async def run_debate(
    *,
    pipeline: str,
    router: LLMRouter,
    memory_store: MemoryStorePort,
    context: dict[str, Any],
    triggered_by: str,
    max_rounds: int | None = None,
) -> DebateGraph:
    """Run a complete debate for a pipeline. Returns the aggregate DebateGraph."""
    debate_id = str(ULID())
    started = datetime.now()
    effective_max_rounds = max_rounds if max_rounds is not None else _default_max_rounds(pipeline)

    analyst_reports: list[dict[str, Any]] = []
    rounds: list[Round] = []
    verdict: Verdict | None = None
    state = DebateState.RUNNING
    error: str | None = None

    try:
        base_ctx = _build_base_context(context, memory_store, pipeline)
        analyst_reports = await _run_analyst_phase(pipeline, router, base_ctx)
        if analyst_reports:
            base_ctx["analyst_reports"] = analyst_reports

        if is_weekly_pipeline(pipeline):
            state, verdict = await _run_weekly_flow(debate_id, router, base_ctx)
        elif is_news_pipeline(pipeline):
            state, verdict, rounds = await _run_news_flow(
                debate_id, router, base_ctx, effective_max_rounds
            )
        else:
            state, verdict, rounds = await _run_daily_flow(
                debate_id, router, base_ctx, effective_max_rounds
            )

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("debate failed: %s", exc)
        state = DebateState.FAILED
        error = str(exc)

    return DebateGraph(
        id=debate_id,
        pipeline=pipeline,
        state=state,
        rounds=rounds,
        analyst_reports=analyst_reports,
        verdict=verdict,
        started_at=started,
        ended_at=datetime.now(),
        triggered_by=triggered_by,
        error=error,
    )


def _build_base_context(
    context: dict[str, Any],
    memory_store: MemoryStorePort,
    pipeline: str,
) -> dict[str, Any]:
    """Snapshot the input context and inject the memory_context list."""
    memory_context: list[Any] = []
    try:
        from daily_scheduler.application.use_cases.memory_injection import (
            build_memory_context,
        )

        memory_context = build_memory_context(
            store=memory_store,
            tickers=list(context.get("tickers", [])),
            pipeline=pipeline,
            regime=str(context.get("regime", "neutral")),
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Memory failure must not fail the debate.
        logger.warning("memory_injection failed (continuing): %s", exc)

    base_ctx = dict(context)
    base_ctx["memory_context"] = memory_context
    return base_ctx


async def _run_analyst_phase(
    pipeline: str,
    router: LLMRouter,
    base_ctx: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run the parallel analyst pool when the pipeline declares analyst roles."""
    analyst_roles = [r for r in roles_for_pipeline(pipeline) if _is_analyst(r)]
    if not analyst_roles:
        return []
    return await run_analyst_pool(
        analyst_roles=analyst_roles,
        router=router,
        render_prompt=render_agent_prompt,
        context=base_ctx,
    )


async def _run_weekly_flow(
    debate_id: str,
    router: LLMRouter,
    base_ctx: dict[str, Any],
) -> tuple[DebateState, Verdict]:
    """Sequential PERF_ANALYST → LESSONS_RESEARCHER → PM flow."""
    perf = await _run_single(Role.PERF_ANALYST, router, base_ctx)
    base_ctx["perf"] = perf.structured_json
    lessons = await _run_single(Role.LESSONS_RESEARCHER, router, base_ctx)
    base_ctx["lessons"] = lessons.structured_json
    base_ctx["prior_rounds"] = []
    base_ctx["consensus_score"] = None
    pm_speech = await run_pm(
        router=router,
        render_prompt=render_agent_prompt,
        context=base_ctx,
    )
    verdict = _build_verdict(debate_id, DebateState.CONVERGED, pm_speech, [])
    return DebateState.CONVERGED, verdict


async def _run_news_flow(
    debate_id: str,
    router: LLMRouter,
    base_ctx: dict[str, Any],
    max_rounds: int,
) -> tuple[DebateState, Verdict | None, list[Round]]:
    """Editor / Publisher / Judge loop for news pipelines."""
    rounds: list[Round] = []
    state = DebateState.MAX_ROUNDS_DISSENT
    for idx in range(max_rounds):
        base_ctx["prior_rounds"] = rounds
        editor = await run_editor(
            router=router,
            render_prompt=render_agent_prompt,
            context=base_ctx,
        )
        pub_ctx = dict(base_ctx)
        pub_ctx["editor"] = editor.structured_json
        publisher = await run_publisher(
            router=router,
            render_prompt=render_agent_prompt,
            context=pub_ctx,
        )
        score = await run_judge(
            router=router,
            render_prompt=render_agent_prompt,
            context=base_ctx,
            bull=editor,
            bear=publisher,
            prior_rounds=rounds,
        )
        rounds.append(
            Round(index=idx, bull_speech=editor, bear_speech=publisher, judge_score=score)
        )
        if score.converged(
            rule_threshold=JUDGE_RULE_THRESHOLD,
            llm_threshold=JUDGE_LLM_THRESHOLD,
        ):
            state = DebateState.CONVERGED
            break
    verdict: Verdict | None = None
    if rounds:
        verdict = _build_verdict(debate_id, state, rounds[-1].bear_speech, [])
    return state, verdict, rounds


async def _run_daily_flow(
    debate_id: str,
    router: LLMRouter,
    base_ctx: dict[str, Any],
    max_rounds: int,
) -> tuple[DebateState, Verdict, list[Round]]:
    """Bull / Bear / Judge loop followed by Trader / Risk / PM for daily reports."""
    rounds: list[Round] = []
    state = DebateState.MAX_ROUNDS_DISSENT
    for idx in range(max_rounds):
        base_ctx["prior_rounds"] = rounds
        bull = await run_bull(
            router=router,
            render_prompt=render_agent_prompt,
            context=base_ctx,
        )
        bear_ctx = dict(base_ctx)
        bear_ctx["bull"] = bull.structured_json
        bear = await run_bear(
            router=router,
            render_prompt=render_agent_prompt,
            context=bear_ctx,
        )
        score = await run_judge(
            router=router,
            render_prompt=render_agent_prompt,
            context=base_ctx,
            bull=bull,
            bear=bear,
            prior_rounds=rounds,
        )
        rounds.append(Round(index=idx, bull_speech=bull, bear_speech=bear, judge_score=score))
        if score.converged(
            rule_threshold=JUDGE_RULE_THRESHOLD,
            llm_threshold=JUDGE_LLM_THRESHOLD,
        ):
            state = DebateState.CONVERGED
            break

    pm_speech = await _run_decision_chain(router, base_ctx, rounds)
    verdict = _build_verdict(debate_id, state, pm_speech, [])
    return state, verdict, rounds


async def _run_decision_chain(
    router: LLMRouter,
    base_ctx: dict[str, Any],
    rounds: list[Round],
) -> Speech:
    """Run Trader → RiskMgmt → PortfolioMgr sequentially for daily reports."""
    base_ctx["prior_rounds"] = rounds
    base_ctx["consensus_score"] = (
        rounds[-1].judge_score
        if rounds
        else ConsensusScore(
            rule_score=0.0,
            llm_score=0.0,
            false_consensus=False,
            next_round_questions=[],
            dimensions={},
        )
    )
    trader = await run_trader(
        router=router,
        render_prompt=render_agent_prompt,
        context=base_ctx,
    )
    base_ctx["trader"] = trader.structured_json
    risk = await run_risk_mgmt(
        router=router,
        render_prompt=render_agent_prompt,
        context=base_ctx,
    )
    base_ctx["risk"] = risk.structured_json
    return await run_pm(
        router=router,
        render_prompt=render_agent_prompt,
        context=base_ctx,
    )


def _is_analyst(role: Role) -> bool:
    """Return True for roles that run in the parallel analyst pool."""
    return role in (
        Role.KR_FUNDAMENTALS,
        Role.US_FUNDAMENTALS,
        Role.KR_TECHNICAL,
        Role.US_TECHNICAL,
        Role.NEWS_SENT,
    )


def _default_max_rounds(pipeline: str) -> int:
    """Pick the per-pipeline max-rounds default from the constants module."""
    if pipeline == "daily":
        return MAX_DEBATE_ROUNDS_DAILY
    if pipeline in ("news", "global-news"):
        return MAX_DEBATE_ROUNDS_NEWS
    return max(MAX_DEBATE_ROUNDS_WEEKLY, 1)


def _build_verdict(
    debate_id: str,
    state: DebateState,
    pm_speech: Speech,
    recommendation_dicts: list[dict[str, Any]],
) -> Verdict:
    """Build a Verdict from the PM speech that feeds the legacy parser."""
    payload = dict(pm_speech.structured_json)
    recs = payload.get("recommendations", []) or recommendation_dicts
    return Verdict(
        debate_id=debate_id,
        consensus=state,
        report_content_json=payload,
        recommendation_dicts=recs if isinstance(recs, list) else [],
    )


async def _run_single(role: Role, router: LLMRouter, ctx: dict[str, Any]) -> Speech:
    """One-shot agent invocation (used by weekly sequential flow)."""
    from daily_scheduler.infrastructure.adapters.debate.bull_bear_nodes import (
        _parse_or_empty,
    )

    provider, binding = router.resolve(role)
    prompt = render_agent_prompt(role, ctx)
    result = await provider.submit(
        prompt,
        tools=None,
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
