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


def test_judge_default_uses_codex_for_cross_model_diversity() -> None:
    # Judge runs on Codex/GPT-5.5 — a different model family from the Claude
    # debaters is the strongest lever against self-agreement bias.
    b = default_binding_for(Role.JUDGE)
    assert b.provider is Provider.CODEX
    assert b.model == "gpt-5.5"


def test_trader_and_risk_use_codex_gpt5() -> None:
    # Trader + Risk provide an independent decision lens on GPT-5.5; both are
    # intermediate roles (consumed by the Portfolio Manager) and need no tools.
    for role in (Role.TRADER, Role.RISK_MGMT):
        b = default_binding_for(role)
        assert b.provider is Provider.CODEX
        assert b.model == "gpt-5.5"
        assert tools_for_role(role) == []


def test_portfolio_manager_stays_claude_for_final_report_json() -> None:
    # The PM emits the final structured report JSON → keep it on Claude opus.
    b = default_binding_for(Role.PORTFOLIO_MGR)
    assert b.provider is Provider.CLAUDE_CODE
    assert tools_for_role(Role.PORTFOLIO_MGR) == []


def test_news_roles() -> None:
    for role in (Role.EDITOR, Role.PUBLISHER):
        b = default_binding_for(role)
        assert b.provider is Provider.CLAUDE_CODE
