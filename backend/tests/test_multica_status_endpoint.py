"""Status endpoint for /api/multica."""

from __future__ import annotations

from fastapi.testclient import TestClient

from daily_scheduler.entrypoints.api.app import create_app


def test_status_disabled_when_base_url_empty(monkeypatch) -> None:
    """Without MULTICA_BASE_URL the endpoint reports the integration as disabled."""
    monkeypatch.setenv("MULTICA_BASE_URL", "")
    with TestClient(create_app()) as client:
        response = client.get("/api/multica/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"enabled": False, "up": False, "url": None}


def test_status_enabled_reports_url(monkeypatch) -> None:
    """With MULTICA_BASE_URL set the endpoint reports the URL.

    The remote service is unreachable in the test environment, so ``up`` is
    ``False`` — the integration is *enabled* but cannot be probed. With no
    dedicated MULTICA_WEB_URL, the iframe URL falls back to the base URL.
    """
    monkeypatch.setenv("MULTICA_BASE_URL", "http://multica-backend.invalid:8080")
    monkeypatch.setenv("MULTICA_WEB_URL", "")  # no web URL → fall back to base URL
    with TestClient(create_app()) as client:
        response = client.get("/api/multica/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["url"] == "http://multica-backend.invalid:8080"
    assert payload["up"] is False
    assert set(payload.keys()) == {"enabled", "up", "url"}
    assert isinstance(payload["enabled"], bool)
    assert isinstance(payload["up"], bool)
