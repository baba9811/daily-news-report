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
    result of a live health probe, and ``url`` is the base URL used by the
    iframe page (``None`` when disabled).
    """
    settings = get_settings()
    if not settings.multica_base_url:
        return {"enabled": False, "up": False, "url": None}
    client = MulticaHTTPClient(base_url=settings.multica_base_url)
    up = await client.health()
    return {"enabled": True, "up": up, "url": settings.multica_base_url}
