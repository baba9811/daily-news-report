"""Tests for /api/memory endpoints."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from daily_scheduler.config import Settings
from daily_scheduler.database import get_db, init_database
from daily_scheduler.entrypoints.api.app import create_app

# Importing the persistence + memory model modules registers their ORM tables
# with ``Base.metadata`` before we call ``create_all``.
from daily_scheduler.infrastructure.adapters.persistence import (  # noqa: F401
    models as _persistence_models,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """TestClient with an in-memory SQLite DB and a temp memory directory."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "data" / "daily_scheduler.db"

    def fake_get_settings() -> Settings:
        return Settings(database_url=f"sqlite:///{db_file}")

    # Patch every consumer of ``get_settings`` so the memory store builds
    # against the temp directory.
    monkeypatch.setattr(
        "daily_scheduler.config.get_settings",
        fake_get_settings,
    )
    monkeypatch.setattr(
        "daily_scheduler.infrastructure.dependencies.get_settings",
        fake_get_settings,
    )

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


def test_memory_tree_returns_root(client: TestClient) -> None:
    """GET /api/memory/tree returns a shape with a ``root`` key."""
    response = client.get("/api/memory/tree")
    assert response.status_code == 200
    body = response.json()
    assert "root" in body


def test_memory_search_empty(client: TestClient) -> None:
    """GET /api/memory/search with a non-matching query returns no items."""
    response = client.get("/api/memory/search", params={"q": "nothingmatches"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []


def test_memory_search_blank_query_returns_empty(client: TestClient) -> None:
    """A blank query returns no items without raising."""
    response = client.get("/api/memory/search", params={"q": ""})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []


def test_memory_file_not_found(client: TestClient) -> None:
    """GET /api/memory/file with a missing path returns 404."""
    response = client.get("/api/memory/file", params={"path": "does/not/exist.md"})
    assert response.status_code == 404


def test_memory_file_rejects_path_traversal(client: TestClient) -> None:
    """Path traversal attempts (``..``) must be rejected with 404."""
    response = client.get("/api/memory/file", params={"path": "../etc/passwd"})
    assert response.status_code == 404
