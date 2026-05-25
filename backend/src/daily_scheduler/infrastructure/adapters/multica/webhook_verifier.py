"""HMAC-SHA256 webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac


def verify_webhook(body: bytes, signature_header: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 verification.

    ``signature_header`` is expected in the GitHub-style ``sha256=<hex>`` form.
    Returns ``False`` when the secret is empty (no shared secret means no trust)
    or the header is malformed. Comparison uses ``hmac.compare_digest`` to
    avoid timing side-channels.
    """
    if not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    provided_hex = signature_header[len("sha256=") :]
    expected_hex = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(provided_hex, expected_hex)
    except (ValueError, TypeError):
        return False
