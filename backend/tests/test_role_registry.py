"""Tests for default role → BackendBinding map."""

from __future__ import annotations

from daily_scheduler.domain.entities.agent import Provider, Role
from daily_scheduler.infrastructure.adapters.council.role_registry import (
    default_binding_for,
    tools_for_role,
)


def test_analyst_defaults_use_claude_code_with_websearch_tools() -> None:
    for role in (
        Role.KR_FUNDAMENTALS,
        Role.US_FUNDAMENTALS,
        Role.KR_TECHNICAL,
        Role.US_TECHNICAL,
        Role.NEWS_SENT,
    ):
        b = default_binding_for(role)
        assert b.provider is Provider.CLAUDE_CODE
        assert "WebSearch" in tools_for_role(role)


def test_judge_default_uses_claude_code_distinct_model() -> None:
    # Judge defaults to claude-code (codex requires explicit ChatGPT model
    # config); a distinct model from the debaters' opus still reduces bias.
    b = default_binding_for(Role.JUDGE)
    assert b.provider is Provider.CLAUDE_CODE
    assert b.model == "sonnet"


def test_decision_roles_use_claude_code_no_tools() -> None:
    for role in (Role.TRADER, Role.RISK_MGMT, Role.PORTFOLIO_MGR):
        b = default_binding_for(role)
        assert b.provider is Provider.CLAUDE_CODE
        assert tools_for_role(role) == []


def test_news_roles() -> None:
    for role in (Role.EDITOR, Role.PUBLISHER):
        b = default_binding_for(role)
        assert b.provider is Provider.CLAUDE_CODE
