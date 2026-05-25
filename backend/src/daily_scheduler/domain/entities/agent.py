"""Agent / Role / BackendBinding -- the agent-side domain model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    KR_FUNDAMENTALS = "kr_fundamentals"
    US_FUNDAMENTALS = "us_fundamentals"
    KR_TECHNICAL = "kr_technical"
    US_TECHNICAL = "us_technical"
    NEWS_SENT = "news_sent"
    BULL = "bull"
    BEAR = "bear"
    JUDGE = "judge"
    TRADER = "trader"
    RISK_MGMT = "risk_mgmt"
    PORTFOLIO_MGR = "portfolio_mgr"
    EDITOR = "editor"
    PUBLISHER = "publisher"
    PERF_ANALYST = "perf_analyst"
    LESSONS_RESEARCHER = "lessons_researcher"


class Provider(StrEnum):
    CLAUDE_CODE = "claude-code"
    CODEX = "codex"


@dataclass(frozen=True, slots=True)
class BackendBinding:
    provider: Provider
    model: str
    system_prompt_override: str | None = None
    timeout_s: int = 600


@dataclass(frozen=True, slots=True)
class Agent:
    role: Role
    binding: BackendBinding
    display_name: str
    description: str = ""


_PIPELINE_ROLES: dict[str, tuple[Role, ...]] = {
    "daily": (
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
    ),
    "news": (
        Role.NEWS_SENT,
        Role.KR_TECHNICAL,
        Role.EDITOR,
        Role.PUBLISHER,
        Role.JUDGE,
    ),
    "global-news": (
        Role.NEWS_SENT,
        Role.US_TECHNICAL,
        Role.EDITOR,
        Role.PUBLISHER,
        Role.JUDGE,
    ),
    "weekly": (
        Role.PERF_ANALYST,
        Role.LESSONS_RESEARCHER,
        Role.PORTFOLIO_MGR,
    ),
}


def roles_for_pipeline(pipeline: str) -> tuple[Role, ...]:
    return _PIPELINE_ROLES[pipeline]
