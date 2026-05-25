"""SSE broadcaster — wraps DebateBus events into sse-starlette EventSourceResponse."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from sse_starlette.sse import EventSourceResponse

from daily_scheduler.constants import SSE_KEEPALIVE_INTERVAL_S
from daily_scheduler.domain.ports.debate_bus import DebateBusPort


def make_event_source_response(
    bus: DebateBusPort,
    debate_id: str,
) -> EventSourceResponse:
    """Build an SSE response that streams DebateBus events for ``debate_id``."""

    async def gen() -> AsyncGenerator[dict[str, Any], None]:
        try:
            async for event in bus.subscribe(debate_id):
                yield {
                    "event": event.kind,
                    "data": json.dumps(event.payload, ensure_ascii=False),
                }
                if event.kind in ("debate_done", "error"):
                    break
        except asyncio.CancelledError:
            return

    return EventSourceResponse(
        gen(),
        ping=SSE_KEEPALIVE_INTERVAL_S,
        headers={"cache-control": "no-cache"},
    )
