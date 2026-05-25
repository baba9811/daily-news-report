"""Tests for /api/agents endpoints."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from daily_scheduler.database import get_db, init_database
from daily_scheduler.entrypoints.api.app import create_app

# Importing the persistence + memory model modules registers their ORM tables
# with ``Base.metadata`` before we call ``create_all``.
from daily_scheduler.infrastructure.adapters.persistence import (  # noqa: F401
    models as _persistence_models,
)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient with an in-memory SQLite database bound to get_db."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_database(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def test_list_agents(client: TestClient) -> None:
    """GET /api/agents returns all roles with bindings, tools, and pipelines."""
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["items"], list)
    roles = {item["role"] for item in data["items"]}
    assert "bull" in roles and "judge" in roles
    # All 15 roles exist
    assert len(roles) == 15


def test_get_single_agent(client: TestClient) -> None:
    """GET /api/agents/{role} returns binding + tools for a known role."""
    response = client.get("/api/agents/bull")
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "bull"
    assert "binding" in data
    assert data["binding"]["provider"] in ("claude-code", "codex")


def test_get_unknown_agent_returns_404(client: TestClient) -> None:
    """GET /api/agents/{role} returns 404 for unknown roles."""
    response = client.get("/api/agents/not-a-real-role")
    assert response.status_code == 404


def test_update_binding(client: TestClient) -> None:
    """PUT /api/agents/{role}/binding updates the persisted override."""
    response = client.put(
        "/api/agents/bull/binding",
        json={
            "provider": "codex",
            "model": "gpt-5-codex",
            "system_prompt_override": None,
            "timeout_s": 600,
        },
    )
    assert response.status_code in (200, 204)
    refetch = client.get("/api/agents/bull")
    assert refetch.json()["binding"]["provider"] == "codex"
    assert refetch.json()["binding"]["model"] == "gpt-5-codex"


def test_update_binding_invalid_provider(client: TestClient) -> None:
    """PUT with an invalid provider returns 400."""
    response = client.put(
        "/api/agents/bull/binding",
        json={
            "provider": "not-a-provider",
            "model": "x",
            "system_prompt_override": None,
            "timeout_s": 600,
        },
    )
    assert response.status_code == 400
