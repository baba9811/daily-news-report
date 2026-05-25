"""HMAC-SHA256 verifier for inbound Multica webhooks."""

from __future__ import annotations

import hashlib
import hmac

from daily_scheduler.infrastructure.adapters.multica.webhook_verifier import (
    verify_webhook,
)


def test_correct_signature_verifies() -> None:
    secret = "topsecret"
    body = b'{"event":"test"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook(body, sig, secret) is True


def test_wrong_signature_fails() -> None:
    assert verify_webhook(b"x", "sha256=ffff", "secret") is False


def test_malformed_signature_fails() -> None:
    assert verify_webhook(b"x", "not-an-hmac", "secret") is False


def test_empty_secret_disables_verification() -> None:
    """When secret is empty, verifier returns False (must reject)."""
    assert verify_webhook(b"x", "sha256=anything", "") is False
