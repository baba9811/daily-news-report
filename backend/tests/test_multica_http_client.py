"""MulticaHTTPClient — best-effort HTTP integration with the Multica board."""

from __future__ import annotations

import json

import httpx
import pytest
from daily_scheduler.infrastructure.adapters.multica.http_client import (
    MulticaHTTPClient,
)


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_create_issue_success() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/issues"
        body = json.loads(req.content)
        return httpx.Response(
            201,
            json={
                "id": "i1",
                "title": body["title"],
                "labels": body["labels"],
                "assignee": None,
            },
        )

    client = MulticaHTTPClient(
        base_url="http://mc",
        transport=_transport(handler),
        timeout_s=2,
    )
    issue = await client.create_issue(title="t", body="b", labels=["dissent"])
    assert issue is not None
    assert issue.id == "i1"


@pytest.mark.asyncio
async def test_create_issue_returns_none_on_http_error() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = MulticaHTTPClient(
        base_url="http://mc",
        transport=_transport(handler),
        timeout_s=2,
    )
    assert (await client.create_issue(title="t", body="b", labels=[])) is None


@pytest.mark.asyncio
async def test_health_check() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    client = MulticaHTTPClient(
        base_url="http://mc",
        transport=_transport(handler),
        timeout_s=2,
    )
    assert await client.health() is True


@pytest.mark.asyncio
async def test_disabled_when_base_url_empty() -> None:
    client = MulticaHTTPClient(base_url="", transport=None, timeout_s=2)
    assert await client.health() is False
    assert (await client.create_issue(title="t", body="b", labels=[])) is None
