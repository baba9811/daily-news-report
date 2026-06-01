"""Tests that the new factories return correctly-wired adapters."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from daily_scheduler.database import Base
from daily_scheduler.infrastructure.adapters.llm.claude_code_provider import (
    ClaudeCodeProvider,
)
from daily_scheduler.infrastructure.adapters.llm.codex_provider import CodexProvider
from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import SubprocessPool
from daily_scheduler.infrastructure.adapters.memory.memory_store import MemoryStore
from daily_scheduler.infrastructure.adapters.memory.models import (
    create_memory_fts_table,
)
from daily_scheduler.infrastructure.dependencies import (
    get_claude_code_provider,
    get_codex_provider,
    get_memory_store,
    get_subprocess_pool,
)


@pytest.fixture
def session_factory(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Base.metadata.create_all(eng)
    create_memory_fts_table(eng)
    return lambda: Session(eng), tmp_path, eng


def test_get_subprocess_pool_is_singleton() -> None:
    p1 = get_subprocess_pool()
    p2 = get_subprocess_pool()
    assert p1 is p2
    assert isinstance(p1, SubprocessPool)


def test_get_claude_code_provider_returns_provider() -> None:
    provider = get_claude_code_provider()
    assert isinstance(provider, ClaudeCodeProvider)


def test_get_codex_provider_returns_provider() -> None:
    provider = get_codex_provider()
    assert isinstance(provider, CodexProvider)


def test_get_memory_store_returns_wired_store(session_factory) -> None:
    sf, tmp_path, eng = session_factory
    store = get_memory_store(session_factory=sf, engine=eng, memory_root=tmp_path / "mem")
    assert isinstance(store, MemoryStore)


# --- Plan 2: council wiring ---


def test_get_report_provider_returns_council_provider(session_factory, monkeypatch) -> None:
    """With Multica disabled, the factory returns the in-process CouncilReportProvider."""
    from daily_scheduler.infrastructure import dependencies as deps
    from daily_scheduler.infrastructure.adapters.council.council_report_provider import (
        CouncilReportProvider,
    )

    # Disable Multica explicitly so the test is deterministic regardless of a
    # live stack in the developer's .env.
    patched = deps.get_settings().model_copy(update={"multica_base_url": ""})
    monkeypatch.setattr(deps, "get_settings", lambda: patched)
    sf, tmp_path, eng = session_factory
    provider = deps.get_report_provider(
        session_factory=sf, engine=eng, memory_root=tmp_path / "mem"
    )
    assert isinstance(provider, CouncilReportProvider)


def test_get_report_provider_uses_squad_when_configured(session_factory, monkeypatch) -> None:
    """With Multica + a squad id configured, the daily report runs via the squad."""
    from daily_scheduler.infrastructure import dependencies as deps
    from daily_scheduler.infrastructure.adapters.council.multica_squad_report_provider import (
        MulticaSquadReportProvider,
    )

    # Keep all real settings; override only the Multica fields (squad id set so
    # no network resolution is needed).
    patched = deps.get_settings().model_copy(
        update={
            "multica_base_url": "http://multica.test",
            "multica_api_token": "tok",
            "multica_workspace_id": "ws",
            "multica_squad_id": "squad-uuid",
        }
    )
    monkeypatch.setattr(deps, "get_settings", lambda: patched)
    sf, tmp_path, eng = session_factory
    provider = deps.get_report_provider(
        session_factory=sf, engine=eng, memory_root=tmp_path / "mem"
    )
    assert isinstance(provider, MulticaSquadReportProvider)


def test_get_agent_binding_repo(session_factory) -> None:
    from daily_scheduler.infrastructure.adapters.persistence.agent_binding_repository import (
        SQLAlchemyAgentBindingRepository,
    )
    from daily_scheduler.infrastructure.dependencies import get_agent_binding_repo

    sf, _tmp_path, _eng = session_factory
    session = sf()
    try:
        repo = get_agent_binding_repo(session)
        assert isinstance(repo, SQLAlchemyAgentBindingRepository)
    finally:
        session.close()
