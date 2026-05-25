"""Tests for /api/settings/health (CLI + Multica status)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from daily_scheduler.entrypoints.api.app import create_app


def test_health_returns_cli_status() -> None:
    """The endpoint always returns the three top-level keys."""
    with TestClient(create_app()) as client:
        response = client.get("/api/settings/health")
        assert response.status_code == 200
        data = response.json()
        # Keys exist regardless of CLI availability
        assert "claude_cli" in data
        assert "codex_cli" in data
        assert "multica" in data


def test_health_claude_cli_shape() -> None:
    """claude_cli payload always carries available / path / version keys."""
    with TestClient(create_app()) as client:
        data = client.get("/api/settings/health").json()
    claude = data["claude_cli"]
    assert "available" in claude
    assert "path" in claude
    assert "version" in claude
    assert isinstance(claude["available"], bool)


def test_health_codex_cli_shape() -> None:
    """codex_cli payload always carries available / path / version keys."""
    with TestClient(create_app()) as client:
        data = client.get("/api/settings/health").json()
    codex = data["codex_cli"]
    assert "available" in codex
    assert "path" in codex
    assert "version" in codex
    assert isinstance(codex["available"], bool)


def test_health_multica_shape() -> None:
    """multica payload always carries enabled / up keys."""
    with TestClient(create_app()) as client:
        data = client.get("/api/settings/health").json()
    multica = data["multica"]
    assert "enabled" in multica
    assert "up" in multica
    assert isinstance(multica["enabled"], bool)
    assert isinstance(multica["up"], bool)
