"""Tests for config and timezone utilities."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

from daily_scheduler import tz
from daily_scheduler.config import PROJECT_ROOT, Settings


class TestSettings:
    def test_default_values(self):
        settings = Settings()
        assert settings.smtp_host == "smtp.gmail.com"
        assert settings.smtp_port == 587
        assert settings.report_language == "ko"
        assert settings.timezone == "Asia/Seoul"

    def test_db_path_absolute(self):
        settings = Settings(database_url="sqlite:////absolute/path/db.sqlite3")
        assert settings.db_path == Path("/absolute/path/db.sqlite3")
        assert settings.db_path.is_absolute()

    def test_db_path_relative_resolved_to_project_root(self):
        settings = Settings(database_url="sqlite:///data/test.db")
        expected = PROJECT_ROOT / "data" / "test.db"
        assert settings.db_path == expected
        assert settings.db_path.is_absolute()

    def test_email_to_parses_json_string(self):
        settings = Settings(email_to='["a@b.com", "c@d.com"]')  # type: ignore[arg-type]
        assert settings.email_to == ["a@b.com", "c@d.com"]

    def test_email_to_parses_plain_string(self):
        settings = Settings(email_to="single@example.com")  # type: ignore[arg-type]
        assert settings.email_to == ["single@example.com"]

    def test_email_to_empty_string(self):
        settings = Settings(email_to="")  # type: ignore[arg-type]
        assert settings.email_to == []

    def test_email_to_accepts_list(self):
        settings = Settings(email_to=["a@b.com"])
        assert settings.email_to == ["a@b.com"]

    def test_project_root_is_correct(self):
        assert (PROJECT_ROOT / "backend").is_dir()
        assert (PROJECT_ROOT / "frontend").is_dir()


class TestTimezone:
    def test_now_returns_aware_datetime(self):
        result = tz.now()
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_today_returns_date(self):
        result = tz.today()
        assert isinstance(result, date)

    def test_combine_date_only(self):
        d = date(2026, 3, 17)
        result = tz.combine(d)
        assert isinstance(result, datetime)
        assert result.date() == d
        assert result.tzinfo is not None

    def test_combine_with_time(self):
        d = date(2026, 3, 17)
        t = time(14, 30)
        result = tz.combine(d, t)
        assert result.hour == 14
        assert result.minute == 30


# --- multi-agent council constants ---


def test_max_concurrent_llm_calls_constant() -> None:
    from daily_scheduler.constants import MAX_CONCURRENT_LLM_CALLS

    assert isinstance(MAX_CONCURRENT_LLM_CALLS, int)
    assert MAX_CONCURRENT_LLM_CALLS >= 1


def test_cli_timeout_constants() -> None:
    from daily_scheduler.constants import (
        CLI_TIMEOUT_ANALYST_S,
        CLI_TIMEOUT_DEBATE_S,
        CLI_TIMEOUT_DECISION_S,
        CLI_TIMEOUT_JUDGE_S,
    )

    assert CLI_TIMEOUT_ANALYST_S >= 60
    assert CLI_TIMEOUT_DEBATE_S >= 60
    assert CLI_TIMEOUT_DECISION_S >= 60
    assert CLI_TIMEOUT_JUDGE_S >= 60


def test_judge_thresholds() -> None:
    from daily_scheduler.constants import JUDGE_LLM_THRESHOLD, JUDGE_RULE_THRESHOLD

    assert 0.0 < JUDGE_RULE_THRESHOLD < 1.0
    assert 0.0 < JUDGE_LLM_THRESHOLD < 1.0


def test_memory_constants() -> None:
    from daily_scheduler.constants import (
        MEMORY_AUTO_INJECT_TOP_K,
        MEMORY_TREE_MAX_BYTES,
    )

    assert MEMORY_TREE_MAX_BYTES >= 10_000
    assert 1 <= MEMORY_AUTO_INJECT_TOP_K <= 20


def test_debate_round_constants() -> None:
    from daily_scheduler.constants import (
        MAX_DEBATE_ROUNDS_DAILY,
        MAX_DEBATE_ROUNDS_NEWS,
        MAX_DEBATE_ROUNDS_WEEKLY,
    )

    assert MAX_DEBATE_ROUNDS_DAILY >= 1
    assert MAX_DEBATE_ROUNDS_NEWS >= 1
    assert MAX_DEBATE_ROUNDS_WEEKLY >= 0


def test_codex_settings_defaults() -> None:
    from daily_scheduler.config import get_settings

    s = get_settings()
    assert s.codex_cli_path
    assert s.codex_default_model


def test_multica_settings_defaults() -> None:
    from daily_scheduler.config import get_settings

    s = get_settings()
    assert hasattr(s, "multica_base_url")
    assert hasattr(s, "multica_webhook_secret")
    assert s.multica_base_url == ""  # disabled by default
