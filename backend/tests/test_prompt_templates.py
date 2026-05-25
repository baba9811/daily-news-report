"""Tests for agent prompt template loader."""

from __future__ import annotations

from daily_scheduler.domain.entities.agent import Role
from daily_scheduler.infrastructure.adapters.council.prompt_templates import (
    render_agent_prompt,
)


def test_loader_renders_for_each_role() -> None:
    """Every role's template renders against a canned daily-pipeline context."""
    ctx = {
        "pipeline": "daily",
        "date": "2026-05-25",
        "market_data": "KOSPI flat",
        "screening": "no candidates",
        "retrospective": "win rate 60%",
        "memory_context": [],
        "analyst_reports": [],
        "prior_rounds": [],
        "consensus_score": None,
    }
    for role in Role:
        out = render_agent_prompt(role, ctx)
        assert isinstance(out, str)
        assert len(out) > 0
