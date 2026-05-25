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
    x_multica_signature: str = Header(default=""),
) -> dict[str, Any]:
    """Receive inbound Multica events.

    The endpoint enforces HMAC-SHA256 verification via the
    ``X-Multica-Signature`` header. ``issue.assigned`` events labelled
    ``manual-trigger`` whose title matches ``rerun <pipeline>`` are
    acknowledged so the operator can re-run a pipeline from Multica.
    """
    settings = get_settings()
    body = await request.body()
    if not verify_webhook(body, x_multica_signature, settings.multica_webhook_secret):
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
