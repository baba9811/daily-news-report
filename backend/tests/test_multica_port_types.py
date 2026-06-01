"""Structural tests for the extended MulticaPort dataclasses."""

from __future__ import annotations

from daily_scheduler.domain.ports.multica import (
    MulticaComment,
    MulticaIssueState,
    MulticaRun,
)


def test_issue_state_dataclass() -> None:
    state = MulticaIssueState(id="i1", status="in_review")
    assert state.id == "i1"
    assert state.status == "in_review"


def test_comment_dataclass() -> None:
    comment = MulticaComment(id="c1", author_type="agent", author_id="a1", content="hi")
    assert comment.author_type == "agent"
    assert comment.content == "hi"


def test_run_dataclass() -> None:
    run = MulticaRun(id="r1", agent_id="a1", kind="direct", status="completed")
    assert run.kind == "direct"
    assert run.status == "completed"
