"""MulticaHTTPClient — best-effort HTTP integration with Multica."""

from __future__ import annotations

import logging

import httpx

from daily_scheduler.constants import MULTICA_HTTP_TIMEOUT_S, MULTICA_RETRY_COUNT
from daily_scheduler.domain.ports.multica import MulticaIssue, MulticaPort

logger = logging.getLogger(__name__)


class MulticaHTTPClient(MulticaPort):
    """HTTP client that posts to a running Multica service.

    The client is best-effort: connection / HTTP / parsing errors are logged
    and converted into falsy return values. An empty ``base_url`` disables the
    integration entirely.
    """

    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_s: int = MULTICA_HTTP_TIMEOUT_S,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        """Return True when a base URL has been configured."""
        return bool(self._base_url)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_s,
            transport=self._transport,
        )

    async def health(self) -> bool:
        if not self.enabled:
            return False
        try:
            async with self._client() as client:
                response = await client.get("/api/health")
            return response.status_code == 200
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("multica health failed: %s", exc)
            return False

    async def create_issue(
        self,
        *,
        title: str,
        body: str,
        labels: list[str],
    ) -> MulticaIssue | None:
        if not self.enabled:
            return None
        payload = {"title": title, "body": body, "labels": labels}
        for attempt in range(MULTICA_RETRY_COUNT + 1):
            try:
                async with self._client() as client:
                    response = await client.post("/api/issues", json=payload)
                if response.status_code in (200, 201):
                    data = response.json()
                    return MulticaIssue(
                        id=str(data.get("id", "")),
                        title=str(data.get("title", title)),
                        labels=tuple(data.get("labels", labels) or []),
                        assignee=data.get("assignee"),
                    )
                logger.warning("multica create_issue HTTP %s", response.status_code)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning(
                    "multica create_issue attempt %d failed: %s",
                    attempt + 1,
                    exc,
                )
                if attempt == MULTICA_RETRY_COUNT:
                    break
        return None

    async def add_comment(self, *, issue_id: str, body: str) -> bool:
        if not self.enabled:
            return False
        try:
            async with self._client() as client:
                response = await client.post(
                    f"/api/issues/{issue_id}/comments",
                    json={"body": body},
                )
            return response.status_code in (200, 201)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("multica add_comment failed: %s", exc)
            return False
