"""Tests for the squad/assignee + read methods of MulticaHTTPClient."""

from __future__ import annotations

import asyncio
import json

import httpx

from daily_scheduler.infrastructure.adapters.multica.http_client import MulticaHTTPClient


def _client(handler) -> MulticaHTTPClient:
    return MulticaHTTPClient(
        "http://multica.test",
        api_token="tok",
        workspace_id="ws",
        transport=httpx.MockTransport(handler),
    )


def test_create_issue_with_squad_assignee_sends_assignee_fields() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(201, json={"id": "i1", "title": "t", "assignee_id": "sq1"})

    issue = asyncio.run(
        _client(handler).create_issue(title="t", body="b", labels=[], assignee_id="sq1")
    )
    assert issue is not None and issue.id == "i1"
    assert seen["assignee_type"] == "squad"
    assert seen["assignee_id"] == "sq1"


def test_create_issue_4xx_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(409, json={"error": "active_duplicate_issue"})

    result = asyncio.run(_client(handler).create_issue(title="t", body="b", labels=[]))
    assert result is None
    assert calls["n"] == 1  # 4xx must not be retried


def test_get_issue_maps_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/issues/i1"
        return httpx.Response(200, json={"id": "i1", "status": "in_review"})

    state = asyncio.run(_client(handler).get_issue(issue_id="i1"))
    assert state is not None and state.status == "in_review"


def test_list_comments_maps_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "comments": [
                    {"id": "c1", "author_type": "agent", "author_id": "a1", "content": "hi"}
                ]
            },
        )

    comments = asyncio.run(_client(handler).list_comments(issue_id="i1"))
    assert len(comments) == 1
    assert comments[0].author_type == "agent" and comments[0].content == "hi"


def test_list_runs_maps_fields_from_bare_array() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"id": "r1", "agent_id": "a1", "kind": "direct", "status": "completed"}],
        )

    runs = asyncio.run(_client(handler).list_runs(issue_id="i1"))
    assert len(runs) == 1
    assert runs[0].kind == "direct" and runs[0].status == "completed"
