"""LangGraph state-graph builders for each pipeline.

Note: Plan 2 implements the debate flow in a hand-written async orchestrator
(`debate_engine.py`) for simplicity and testability. The "graph builder" name
is retained for forward compatibility — a future iteration can swap to
LangGraph's StateGraph if we need built-in checkpoint replay. For now,
LangGraph's SqliteSaver is wired into the orchestrator for state checkpoints.
"""

from __future__ import annotations

from typing import Literal

Pipeline = Literal["daily", "news", "global-news", "weekly"]


def is_news_pipeline(pipeline: str) -> bool:
    return pipeline in ("news", "global-news")


def is_weekly_pipeline(pipeline: str) -> bool:
    return pipeline == "weekly"
