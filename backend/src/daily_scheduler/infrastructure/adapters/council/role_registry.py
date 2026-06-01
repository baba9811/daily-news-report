"""Default BackendBinding and tool list per Role.

The council is a deliberately *heterogeneous* multi-model team. Roles split
along a capability boundary:

* **Claude Code (``claude -p``, opus)** — every role that needs live web
  research (the five analysts, Bull/Bear, Editor/Publisher all carry WebSearch
  tools) plus the Portfolio Manager, whose output is the final structured
  report JSON and therefore prizes formatting reliability.
* **Codex (``codex exec``, GPT-5.5)** — the cross-model *critique / deliberation*
  layer that reasons over context the analysts already gathered and needs no
  web access: the Judge (a different model from the Claude debaters reduces
  self-agreement bias), the Trader and Risk Manager (independent decision
  perspectives), and the weekly Performance Analyst.

The codex provider does not forward WebSearch/WebFetch, so codex roles are
intentionally limited to the tool-free deliberation roles. ``LLMRouter`` falls
back to Claude automatically if the ``codex`` CLI is absent, so the team still
runs end-to-end on a Claude-only host.
"""

from __future__ import annotations

from daily_scheduler.constants import (
    CLI_TIMEOUT_ANALYST_S,
    CLI_TIMEOUT_DEBATE_S,
    CLI_TIMEOUT_DECISION_S,
    CLI_TIMEOUT_JUDGE_S,
)
from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role

_DEFAULTS: dict[Role, BackendBinding] = {
    Role.KR_FUNDAMENTALS: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
        timeout_s=CLI_TIMEOUT_ANALYST_S,
    ),
    Role.US_FUNDAMENTALS: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
        timeout_s=CLI_TIMEOUT_ANALYST_S,
    ),
    Role.KR_TECHNICAL: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
        timeout_s=CLI_TIMEOUT_ANALYST_S,
    ),
    Role.US_TECHNICAL: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
        timeout_s=CLI_TIMEOUT_ANALYST_S,
    ),
    Role.NEWS_SENT: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
        timeout_s=CLI_TIMEOUT_ANALYST_S,
    ),
    Role.BULL: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
        timeout_s=CLI_TIMEOUT_DEBATE_S,
    ),
    Role.BEAR: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
        timeout_s=CLI_TIMEOUT_DEBATE_S,
    ),
    # Judge runs on Codex/GPT-5.5: a different model family from the Claude
    # debaters is the strongest lever against self-agreement bias. It needs no
    # web tools (it only weighs the bull/bear arguments) and its JSON failure
    # mode is safe — judge_node computes a quantitative rule_score in code and
    # degrades a malformed LLM envelope to score 0 (no false convergence).
    Role.JUDGE: BackendBinding(
        provider=Provider.CODEX,
        model="gpt-5.5",
        timeout_s=CLI_TIMEOUT_JUDGE_S,
    ),
    # Trader + Risk run on Codex/GPT-5.5 for an independent decision lens. Both
    # are intermediate (consumed by the Portfolio Manager), so imperfect JSON
    # degrades gracefully via _parse_or_empty.
    Role.TRADER: BackendBinding(
        provider=Provider.CODEX,
        model="gpt-5.5",
        timeout_s=CLI_TIMEOUT_DECISION_S,
    ),
    Role.RISK_MGMT: BackendBinding(
        provider=Provider.CODEX,
        model="gpt-5.5",
        timeout_s=CLI_TIMEOUT_DECISION_S,
    ),
    Role.PORTFOLIO_MGR: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
        timeout_s=CLI_TIMEOUT_DECISION_S,
    ),
    Role.EDITOR: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
        timeout_s=CLI_TIMEOUT_DEBATE_S,
    ),
    Role.PUBLISHER: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
        timeout_s=CLI_TIMEOUT_DEBATE_S,
    ),
    # Performance Analyst (weekly) crunches closed-position stats — numeric
    # reasoning over provided data, no web — a good fit for Codex/GPT-5.5.
    Role.PERF_ANALYST: BackendBinding(
        provider=Provider.CODEX,
        model="gpt-5.5",
        timeout_s=CLI_TIMEOUT_DECISION_S,
    ),
    Role.LESSONS_RESEARCHER: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="sonnet",
        timeout_s=CLI_TIMEOUT_DECISION_S,
    ),
}

_TOOLS: dict[Role, list[str]] = {
    Role.KR_FUNDAMENTALS: ["WebSearch", "WebFetch"],
    Role.US_FUNDAMENTALS: ["WebSearch", "WebFetch"],
    Role.KR_TECHNICAL: ["WebSearch", "WebFetch"],
    Role.US_TECHNICAL: ["WebSearch", "WebFetch"],
    Role.NEWS_SENT: ["WebSearch", "WebFetch"],
    Role.BULL: ["WebSearch"],
    Role.BEAR: ["WebSearch"],
    Role.EDITOR: ["WebSearch"],
    Role.PUBLISHER: ["WebSearch"],
}


def default_binding_for(role: Role) -> BackendBinding:
    """Return the default BackendBinding for the given role."""
    return _DEFAULTS[role]


def tools_for_role(role: Role) -> list[str]:
    """Return a copy of the default tool list for the given role (empty if none)."""
    return list(_TOOLS.get(role, []))
