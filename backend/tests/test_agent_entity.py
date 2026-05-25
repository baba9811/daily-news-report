"""Tests for Agent, Role, BackendBinding entities."""

from __future__ import annotations

import pytest

from daily_scheduler.domain.entities.agent import (
    Agent,
    BackendBinding,
    Provider,
    Role,
)


def test_role_enum_has_all_pipeline_roles() -> None:
    expected = {
        "KR_FUNDAMENTALS",
        "US_FUNDAMENTALS",
        "KR_TECHNICAL",
        "US_TECHNICAL",
        "NEWS_SENT",
        "BULL",
        "BEAR",
        "JUDGE",
        "TRADER",
        "RISK_MGMT",
        "PORTFOLIO_MGR",
        "EDITOR",
        "PUBLISHER",
        "PERF_ANALYST",
        "LESSONS_RESEARCHER",
    }
    assert {r.name for r in Role} == expected


def test_provider_enum() -> None:
    assert Provider.CLAUDE_CODE.value == "claude-code"
    assert Provider.CODEX.value == "codex"


def test_backend_binding_defaults() -> None:
    b = BackendBinding(provider=Provider.CLAUDE_CODE, model="opus")
    assert b.provider is Provider.CLAUDE_CODE
    assert b.model == "opus"
    assert b.system_prompt_override is None
    assert b.timeout_s == 600


def test_agent_dataclass_carries_role_and_binding() -> None:
    a = Agent(
        role=Role.BULL,
        binding=BackendBinding(provider=Provider.CLAUDE_CODE, model="opus"),
        display_name="Bull Researcher",
    )
    assert a.role is Role.BULL
    assert a.binding.provider is Provider.CLAUDE_CODE
    assert a.display_name == "Bull Researcher"


def test_role_pipelines_membership() -> None:
    from daily_scheduler.domain.entities.agent import roles_for_pipeline

    assert set(roles_for_pipeline("daily")) == {
        Role.KR_FUNDAMENTALS,
        Role.US_FUNDAMENTALS,
        Role.KR_TECHNICAL,
        Role.US_TECHNICAL,
        Role.NEWS_SENT,
        Role.BULL,
        Role.BEAR,
        Role.JUDGE,
        Role.TRADER,
        Role.RISK_MGMT,
        Role.PORTFOLIO_MGR,
    }
    assert set(roles_for_pipeline("news")) == {
        Role.NEWS_SENT,
        Role.KR_TECHNICAL,
        Role.EDITOR,
        Role.PUBLISHER,
        Role.JUDGE,
    }
    assert set(roles_for_pipeline("global-news")) == {
        Role.NEWS_SENT,
        Role.US_TECHNICAL,
        Role.EDITOR,
        Role.PUBLISHER,
        Role.JUDGE,
    }
    assert set(roles_for_pipeline("weekly")) == {
        Role.PERF_ANALYST,
        Role.LESSONS_RESEARCHER,
        Role.PORTFOLIO_MGR,
    }
    with pytest.raises(KeyError):
        roles_for_pipeline("unknown")
