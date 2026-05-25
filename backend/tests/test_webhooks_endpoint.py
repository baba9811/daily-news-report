"""HMAC-verified Multica webhook endpoint."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from daily_scheduler.entrypoints.api.app import create_app


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_rejects_missing_signature(monkeypatch) -> None:
    monkeypatch.setenv("MULTICA_WEBHOOK_SECRET", "topsecret")
    with TestClient(create_app()) as client:
        response = client.post("/webhooks/multica", json={"event": "issue.assigned"})
    assert response.status_code == 401


def test_webhook_accepts_valid_signature(monkeypatch) -> None:
    monkeypatch.setenv("MULTICA_WEBHOOK_SECRET", "topsecret")
    body = json.dumps(
        {
            "event": "issue.assigned",
            "issue": {"id": "i1", "labels": [], "title": "test"},
        }
    ).encode()
    with TestClient(create_app()) as client:
        response = client.post(
            "/webhooks/multica",
            content=body,
            headers={
                "X-Multica-Signature": _sign(body, "topsecret"),
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200


def test_webhook_triggers_pipeline_on_manual_trigger_label(monkeypatch) -> None:
    monkeypatch.setenv("MULTICA_WEBHOOK_SECRET", "topsecret")
    body = json.dumps(
        {
            "event": "issue.assigned",
            "issue": {
                "id": "i2",
                "labels": ["manual-trigger"],
                "title": "rerun daily",
            },
        }
    ).encode()
    with TestClient(create_app()) as client:
        response = client.post(
            "/webhooks/multica",
            content=body,
            headers={
                "X-Multica-Signature": _sign(body, "topsecret"),
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("triggered") == "daily"
