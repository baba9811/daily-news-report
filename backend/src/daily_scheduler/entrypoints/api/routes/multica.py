"""Status endpoint for the /multica UI page."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from daily_scheduler.config import get_settings
from daily_scheduler.infrastructure.adapters.multica.http_client import (
    MulticaHTTPClient,
)

router = APIRouter(prefix="/api/multica", tags=["multica"])


@router.get("/status")
async def status() -> dict[str, Any]:
    """Return Multica integration status for the UI.

    The response shape is::

        {"enabled": bool, "up": bool, "url": str | None}

    ``enabled`` reflects whether ``MULTICA_BASE_URL`` is set, ``up`` is the
    result of a live health probe against the backend API, and ``url`` is the
    web (board UI) URL the iframe should load — falling back to the API base
    URL when no dedicated web URL is configured.
    """
    settings = get_settings()
    if not settings.multica_base_url:
        return {"enabled": False, "up": False, "url": None}
    client = MulticaHTTPClient(base_url=settings.multica_base_url)
    up = await client.health()
    iframe_url = settings.multica_web_url or settings.multica_base_url
    return {"enabled": True, "up": up, "url": iframe_url}
