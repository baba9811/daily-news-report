"""Inbound webhooks from Multica."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from daily_scheduler.config import get_settings
from daily_scheduler.infrastructure.adapters.multica.webhook_verifier import (
    verify_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_VALID_PIPELINES: frozenset[str] = frozenset({"daily", "news", "global-news", "weekly"})


@router.post("/multica")
async def multica_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_multica_signature: str = Header(default=""),
) -> dict[str, Any]:
    """Receive inbound Multica events.

    The endpoint enforces HMAC-SHA256 verification. Multica's autopilot
    webhooks sign the body GitHub-style and send it as ``X-Hub-Signature-256``;
    ``X-Multica-Signature`` is accepted as a fallback for compatibility. Both
    use the ``sha256=<hex>`` format. ``issue.assigned`` events labelled
    ``manual-trigger`` whose title matches ``rerun <pipeline>`` are
    acknowledged so the operator can re-run a pipeline from Multica.
    """
    settings = get_settings()
    body = await request.body()
    signature = x_hub_signature_256 or x_multica_signature
    if not verify_webhook(body, signature, settings.multica_webhook_secret):
        logger.warning(
            "multica webhook signature mismatch (body_len=%d)",
            len(body),
        )
        raise HTTPException(status_code=401, detail="invalid signature")

    payload: dict[str, Any] = {}
    if body:
        try:
            decoded = await request.json()
            if isinstance(decoded, dict):
                payload = decoded
        except (ValueError, TypeError):
            payload = {}

    event = payload.get("event")
    logger.info("multica webhook event=%s", event)

    if event == "issue.assigned":
        issue = payload.get("issue") or {}
        labels = set(issue.get("labels", []) or [])
        title = str(issue.get("title", ""))
        if "manual-trigger" in labels and title.startswith("rerun "):
            pipeline = title.removeprefix("rerun ").strip()
            if pipeline in _VALID_PIPELINES:
                logger.info("multica triggered pipeline=%s", pipeline)
                # Defer to the existing /api/pipeline/run mechanism if needed;
                # for Plan 4 we just acknowledge.
                return {"ok": True, "triggered": pipeline}

    return {"ok": True}
