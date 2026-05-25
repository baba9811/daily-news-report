"""Default BackendBinding and tool list per Role."""

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
    Role.JUDGE: BackendBinding(
        provider=Provider.CODEX,
        model="gpt-5-codex",
        timeout_s=CLI_TIMEOUT_JUDGE_S,
    ),
    Role.TRADER: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="sonnet",
        timeout_s=CLI_TIMEOUT_DECISION_S,
    ),
    Role.RISK_MGMT: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="opus",
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
    Role.PERF_ANALYST: BackendBinding(
        provider=Provider.CLAUDE_CODE,
        model="sonnet",
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
