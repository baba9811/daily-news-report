"""Smoke test for SSE endpoint."""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

from daily_scheduler.entrypoints.api.app import create_app
from daily_scheduler.infrastructure.adapters.debate.in_memory_debate_bus import (
    DebateEvent,
)
from daily_scheduler.infrastructure.dependencies import get_debate_bus


def test_sse_endpoint_returns_text_event_stream() -> None:
    """The /api/debate/{id}/stream endpoint emits SSE events from the bus."""
    app = create_app()
    bus = get_debate_bus()
    debate_id = "test-sse-debate"

    def publish_terminal_event() -> None:
        # Give the client a moment to subscribe, then publish a closing event
        time.sleep(0.2)
        bus.publish(debate_id, DebateEvent(kind="debate_done", payload={"state": "CONVERGED"}))

    publisher = threading.Thread(target=publish_terminal_event)
    publisher.start()

    with TestClient(app) as client:
        with client.stream("GET", f"/api/debate/{debate_id}/stream") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            # Read until the stream closes after debate_done
            chunks: list[str] = []
            for chunk in resp.iter_text():
                chunks.append(chunk)
                if "debate_done" in "".join(chunks):
                    break

    publisher.join(timeout=2)
    body = "".join(chunks)
    assert "event: debate_done" in body
    assert "CONVERGED" in body
