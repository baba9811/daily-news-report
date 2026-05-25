"""Hybrid Judge node — rule_score + llm_score + false-consensus detection."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.domain.entities.debate import ConsensusScore, Round, Speech
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

logger = logging.getLogger(__name__)


async def run_judge(
    *,
    router: LLMRouter,
    render_prompt: Callable[[Role, dict[str, Any]], str],
    context: dict[str, Any],
    bull: Speech,
    bear: Speech,
    prior_rounds: list[Round],
) -> ConsensusScore:
    rule_score = _compute_rule_score(bull, bear, prior_rounds)
    fc_rule = _detect_false_consensus_rule(bull, bear, prior_rounds)

    provider, binding = router.resolve(Role.JUDGE)
    judge_context = dict(context)
    judge_context.update(
        {
            "bull_text": bull.text,
            "bear_text": bear.text,
            "bull_struct": bull.structured_json,
            "bear_struct": bear.structured_json,
            "rule_score": rule_score,
            "prior_rounds_count": len(prior_rounds),
        }
    )
    prompt = render_prompt(Role.JUDGE, judge_context)

    try:
        result = await provider.submit(
            prompt,
            tools=None,
            timeout_s=binding.timeout_s,
            model=binding.model,
        )
        envelope = _parse_judge_envelope(result.text)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("judge LLM failed: %s", e)
        envelope = {
            "agreement_score": 0.0,
            "dimensions": {},
            "false_consensus_detected": False,
            "false_consensus_reason": f"judge LLM error: {e}",
        }

    llm_score = float(envelope.get("agreement_score", 0.0))
    fc_llm = bool(envelope.get("false_consensus_detected", False))
    questions = list(envelope.get("dimensions", {}).get("sharpening_questions", []) or [])

    return ConsensusScore(
        rule_score=rule_score,
        llm_score=llm_score,
        false_consensus=fc_rule or fc_llm,
        next_round_questions=questions,
        dimensions=dict(envelope.get("dimensions", {})),
    )


def _compute_rule_score(
    bull: Speech,
    bear: Speech,
    prior_rounds: list[Round],
) -> float:
    b1 = bull.structured_json
    b2 = bear.structured_json

    direction = 1.0 if b1.get("direction") == b2.get("direction") else 0.0

    t1 = set(_as_list(b1.get("top_tickers", [])))
    t2 = set(_as_list(b2.get("top_tickers", [])))
    jaccard = (len(t1 & t2) / len(t1 | t2)) if (t1 | t2) else 0.0

    risk_diff = _risk_distance(b1.get("risk_band"), b2.get("risk_band"))
    risk_score = 1.0 - risk_diff  # 1.0 same, 0.0 max diff

    delta = _stability_vs_prev(bull, bear, prior_rounds)

    return 0.40 * direction + 0.30 * jaccard + 0.20 * risk_score + 0.10 * delta


def _detect_false_consensus_rule(
    bull: Speech,
    bear: Speech,
    prior_rounds: list[Round],
) -> bool:
    if not prior_rounds:
        return False
    prev = prior_rounds[-1]
    prev_bear_len = len(prev.bear_speech.text)
    curr_bear_len = len(bear.text)
    prev_bull_len = len(prev.bull_speech.text)
    curr_bull_len = len(bull.text)

    bear_collapse = prev_bear_len > 0 and curr_bear_len / prev_bear_len < 0.6
    bull_collapse = prev_bull_len > 0 and curr_bull_len / prev_bull_len < 0.6
    direction_flipped = prev.bull_speech.structured_json.get(
        "direction"
    ) != prev.bear_speech.structured_json.get("direction") and bull.structured_json.get(
        "direction"
    ) == bear.structured_json.get("direction")
    return direction_flipped and (bear_collapse or bull_collapse)


def _stability_vs_prev(
    bull: Speech,
    bear: Speech,
    prior_rounds: list[Round],
) -> float:
    if not prior_rounds:
        return 1.0
    prev = prior_rounds[-1]
    bull_same = bull.structured_json.get("direction") == prev.bull_speech.structured_json.get(
        "direction"
    )
    bear_same = bear.structured_json.get("direction") == prev.bear_speech.structured_json.get(
        "direction"
    )
    return 1.0 if (bull_same and bear_same) else 0.5


def _risk_distance(a: object, b: object) -> float:
    ranks = {"LOW": 0, "MID": 1, "HIGH": 2}
    if a not in ranks or b not in ranks:
        return 0.5
    return abs(ranks[a] - ranks[b]) / 2.0


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return []


def _parse_judge_envelope(text: str) -> dict[str, Any]:
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
    return {"agreement_score": 0.0, "dimensions": {}, "false_consensus_detected": False}
