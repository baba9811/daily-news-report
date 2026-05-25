"""Tests for AgentBindingRepository (port + SQLAlchemy adapter)."""

from __future__ import annotations

import pytest
from daily_scheduler.infrastructure.adapters.persistence.agent_binding_repository import (
    SQLAlchemyAgentBindingRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from daily_scheduler.database import Base
from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role


@pytest.fixture
def repo():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        yield SQLAlchemyAgentBindingRepository(s)


def test_get_returns_none_when_no_override(repo) -> None:
    assert repo.get(Role.BULL) is None


def test_upsert_then_get(repo) -> None:
    b = BackendBinding(provider=Provider.CODEX, model="gpt-5-codex", timeout_s=300)
    repo.upsert(Role.JUDGE, b)
    fetched = repo.get(Role.JUDGE)
    assert fetched is not None
    assert fetched.provider is Provider.CODEX
    assert fetched.model == "gpt-5-codex"
    assert fetched.timeout_s == 300


def test_upsert_overwrites(repo) -> None:
    b1 = BackendBinding(provider=Provider.CLAUDE_CODE, model="sonnet")
    b2 = BackendBinding(provider=Provider.CLAUDE_CODE, model="opus")
    repo.upsert(Role.TRADER, b1)
    repo.upsert(Role.TRADER, b2)
    fetched = repo.get(Role.TRADER)
    assert fetched.model == "opus"


def test_delete_removes(repo) -> None:
    b = BackendBinding(provider=Provider.CLAUDE_CODE, model="opus")
    repo.upsert(Role.BULL, b)
    repo.delete(Role.BULL)
    assert repo.get(Role.BULL) is None


def test_list_all(repo) -> None:
    repo.upsert(Role.BULL, BackendBinding(provider=Provider.CLAUDE_CODE, model="opus"))
    repo.upsert(Role.BEAR, BackendBinding(provider=Provider.CLAUDE_CODE, model="opus"))
    all_bindings = dict(repo.list_all())
    assert Role.BULL in all_bindings
    assert Role.BEAR in all_bindings
