"""Tests for MulticaSquadReportProvider (squad happy path + fallbacks)."""

from __future__ import annotations

from datetime import date

from daily_scheduler.domain.ports.multica import (
    MulticaComment,
    MulticaIssue,
    MulticaIssueState,
    MulticaRun,
)
from daily_scheduler.infrastructure.adapters.council.multica_squad_report_provider import (
    MulticaSquadReportProvider,
)

_GOOD_ENVELOPE = (
    "final:\n```json\n"
    '{"market_summary": "S", "report_date": "2026-06-02", '
    '"recommendations": [{"ticker": "005930.KS", "name": "Samsung"}]}\n```'
)


class FakeMultica:
    """Scripts a successful squad run: create -> completed runs -> leader JSON."""

    def __init__(self, *, status: str = "in_review", comment: str = _GOOD_ENVELOPE) -> None:
        self.created: tuple[str, str | None] | None = None
        self._status = status
        self._comment = comment

    async def health(self) -> bool:
        return True

    async def create_issue(self, *, title, body, labels, assignee_id=None):
        self.created = (title, assignee_id)
        return MulticaIssue(id="i1", title=title, labels=tuple(labels), assignee=None)

    async def add_comment(self, *, issue_id, body):
        return True

    async def get_issue(self, *, issue_id):
        return MulticaIssueState(id=issue_id, status=self._status)

    async def list_comments(self, *, issue_id):
        return [MulticaComment(id="c1", author_type="agent", author_id="pm", content=self._comment)]

    async def list_runs(self, *, issue_id):
        return [
            MulticaRun(id="r1", agent_id="pm", kind="direct", status="completed"),
            MulticaRun(id="r2", agent_id="an", kind="comment", status="completed"),
        ]


class StubFallback:
    def generate_daily_report(self, *args, **kwargs):
        return ("FALLBACK_RAW", 0.0)

    def generate_weekly_report(self, *args, **kwargs):
        return ("FALLBACK_WEEKLY", 0.0)


class BoomFallback:
    def generate_daily_report(self, *args, **kwargs):
        raise AssertionError("fallback must not run on success")

    def generate_weekly_report(self, *args, **kwargs):
        raise AssertionError("weekly not under test")


def _provider(multica, fallback, **overrides):
    kwargs = dict(
        multica=multica,
        squad_id="sq1",
        fallback=fallback,
        poll_interval_s=0,
        timeout_s=5,
        quiescence_grace_s=0,
    )
    kwargs.update(overrides)
    return MulticaSquadReportProvider(**kwargs)


def test_happy_path_returns_extracted_report_and_assigns_squad() -> None:
    multica = FakeMultica()
    provider = _provider(multica, BoomFallback())
    raw, elapsed = provider.generate_daily_report(date(2026, 6, 2), "retro")
    assert '"market_summary"' in raw and '"S"' in raw
    assert elapsed >= 0
    assert multica.created is not None and multica.created[1] == "sq1"


def test_falls_back_when_multica_unhealthy() -> None:
    class Down(FakeMultica):
        async def health(self) -> bool:
            return False

        async def create_issue(self, *, title, body, labels, assignee_id=None):
            raise AssertionError("must not create an issue when unhealthy")

    raw, _ = _provider(Down(), StubFallback()).generate_daily_report(date(2026, 6, 2), "retro")
    assert raw == "FALLBACK_RAW"


def test_falls_back_on_timeout_without_terminal_status() -> None:
    class NeverDone(FakeMultica):
        async def get_issue(self, *, issue_id):
            return MulticaIssueState(id=issue_id, status="in_progress")

        async def list_runs(self, *, issue_id):
            return [MulticaRun(id="r1", agent_id="pm", kind="direct", status="running")]

        async def list_comments(self, *, issue_id):
            # Squad still working — no final report posted yet.
            return [MulticaComment(id="c1", author_type="agent", author_id="pm", content="...")]

    provider = _provider(NeverDone(), StubFallback(), timeout_s=0)
    raw, _ = provider.generate_daily_report(date(2026, 6, 2), "retro")
    assert raw == "FALLBACK_RAW"


def test_falls_back_when_no_parseable_report() -> None:
    multica = FakeMultica(comment="just prose, no json envelope here")
    raw, _ = _provider(multica, StubFallback()).generate_daily_report(date(2026, 6, 2), "retro")
    assert raw == "FALLBACK_RAW"


def test_falls_back_when_report_has_no_recommendations() -> None:
    """An abbreviated squad report (summary only, no recommendations) is rejected."""
    multica = FakeMultica(
        comment='```json\n{"market_summary": "S", "report_date": "2026-06-02"}\n```'
    )
    raw, _ = _provider(multica, StubFallback()).generate_daily_report(date(2026, 6, 2), "retro")
    assert raw == "FALLBACK_RAW"


def test_weekly_delegates_to_fallback() -> None:
    raw, _ = _provider(FakeMultica(), StubFallback()).generate_weekly_report(
        date(2026, 6, 2), "stats", "perf"
    )
    assert raw == "FALLBACK_WEEKLY"
