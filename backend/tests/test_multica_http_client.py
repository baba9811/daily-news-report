"""MulticaHTTPClient — best-effort HTTP integration with the Multica board.

The wire format mirrors the Multica self-host backend: PAT Bearer auth, an
``X-Workspace-ID`` header, and ``{title, description, priority, status}`` on
issue creation (no ``body``/``labels`` fields).
"""

from __future__ import annotations

import json

import httpx
import pytest

from daily_scheduler.infrastructure.adapters.multica.http_client import (
    MulticaHTTPClient,
)

_TOKEN = "mul_testtoken"
_WS = "ws-uuid-123"


def _transport(handler):
    return httpx.MockTransport(handler)


def _client(handler) -> MulticaHTTPClient:
    return MulticaHTTPClient(
        base_url="http://mc",
        api_token=_TOKEN,
        workspace_id=_WS,
        transport=_transport(handler),
        timeout_s=2,
    )


@pytest.mark.asyncio
async def test_create_issue_sends_real_payload_and_auth() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/issues"
        assert req.headers.get("Authorization") == f"Bearer {_TOKEN}"
        assert req.headers.get("X-Workspace-ID") == _WS
        body = json.loads(req.content)
        # Real Multica fields — no "body"/"labels".
        assert body["title"] == "t"
        assert "description" in body and "body" not in body and "labels" not in body
        assert body["priority"] == "high"  # "dissent" label → high priority
        assert "— labels: dissent" in body["description"]
        return httpx.Response(
            201,
            json={
                "id": "5530a688",
                "identifier": "DAI-1",
                "title": body["title"],
                "assignee_id": None,
            },
        )

    issue = await _client(handler).create_issue(title="t", body="b", labels=["dissent"])
    assert issue is not None
    assert issue.id == "5530a688"
    assert issue.labels == ("dissent",)


@pytest.mark.asyncio
async def test_create_issue_returns_none_on_http_error() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="missing authorization")

    assert (await _client(handler).create_issue(title="t", body="b", labels=[])) is None


@pytest.mark.asyncio
async def test_add_comment_uses_content_field() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/issues/abc/comments"
        body = json.loads(req.content)
        assert body == {"content": "hello"}
        return httpx.Response(201, json={"id": "c1"})

    assert await _client(handler).add_comment(issue_id="abc", body="hello") is True


@pytest.mark.asyncio
async def test_health_check_needs_no_auth() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/healthz"
        return httpx.Response(200, json={"status": "ok"})

    # Health works with only a base URL (no token/workspace).
    client = MulticaHTTPClient(base_url="http://mc", transport=_transport(handler), timeout_s=2)
    assert await client.health() is True


@pytest.mark.asyncio
async def test_writes_disabled_without_token() -> None:
    """base_url set but no token/workspace → writes are skipped (no 401 spam)."""

    def handler(_req: httpx.Request) -> httpx.Response:  # pragma: no cover — never called
        raise AssertionError("should not POST without credentials")

    client = MulticaHTTPClient(base_url="http://mc", transport=_transport(handler), timeout_s=2)
    assert client.write_enabled is False
    assert (await client.create_issue(title="t", body="b", labels=[])) is None
    assert (await client.add_comment(issue_id="x", body="y")) is False


@pytest.mark.asyncio
async def test_disabled_when_base_url_empty() -> None:
    client = MulticaHTTPClient(base_url="", transport=None, timeout_s=2)
    assert await client.health() is False
    assert (await client.create_issue(title="t", body="b", labels=[])) is None
