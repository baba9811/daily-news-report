"""MulticaHTTPClient — best-effort HTTP integration with Multica.

Wire format matches the Multica self-host backend (``multica-ai/multica``):

* Auth is a Personal Access Token (``mul_...``) sent as ``Authorization:
  Bearer``. Writes are scoped to a workspace via the ``X-Workspace-ID`` header.
* ``POST /api/issues`` takes ``{title, description, priority, status}`` (there
  is no ``body``/``labels`` field — labels are a separate sub-resource, so we
  fold them into ``description`` and map them onto ``priority``).
* ``POST /api/issues/{id}/comments`` takes ``{content}``.
* ``GET /healthz`` is unauthenticated and powers the status probe.
"""

from __future__ import annotations

import logging

import httpx

from daily_scheduler.constants import MULTICA_HTTP_TIMEOUT_S, MULTICA_RETRY_COUNT
from daily_scheduler.domain.ports.multica import MulticaIssue, MulticaPort

logger = logging.getLogger(__name__)

# Map a daily-scheduler label onto a Multica issue priority. Order matters:
# the first matching label wins.
_LABEL_PRIORITY: tuple[tuple[str, str], ...] = (
    ("dissent", "high"),
    ("infra", "medium"),
)
_DEFAULT_PRIORITY = "low"


class MulticaHTTPClient(MulticaPort):
    """HTTP client that posts to a running Multica service.

    The client is best-effort: connection / HTTP / parsing errors are logged
    and converted into falsy return values. An empty ``base_url`` disables the
    integration entirely; missing ``api_token``/``workspace_id`` disables only
    the authenticated write paths (the health probe still works).
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_token: str = "",
        workspace_id: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_s: int = MULTICA_HTTP_TIMEOUT_S,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._workspace_id = workspace_id
        self._transport = transport
        self._timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        """Return True when a base URL has been configured (health probe)."""
        return bool(self._base_url)

    @property
    def write_enabled(self) -> bool:
        """Return True when issues/comments can be authenticated and scoped."""
        return bool(self._base_url and self._api_token and self._workspace_id)

    def _client(self) -> httpx.AsyncClient:
        headers: dict[str, str] = {}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        if self._workspace_id:
            headers["X-Workspace-ID"] = self._workspace_id
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_s,
            transport=self._transport,
            headers=headers or None,
        )

    async def health(self) -> bool:
        if not self.enabled:
            return False
        try:
            async with self._client() as client:
                response = await client.get("/healthz")
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
        if not self.write_enabled:
            if self.enabled:
                logger.warning(
                    "multica create_issue skipped: MULTICA_API_TOKEN / "
                    "MULTICA_WORKSPACE_ID not configured"
                )
            return None
        payload = {
            "title": title,
            "description": _compose_description(body, labels),
            "priority": _priority_for(labels),
            "status": "todo",
        }
        for attempt in range(MULTICA_RETRY_COUNT + 1):
            try:
                async with self._client() as client:
                    response = await client.post("/api/issues", json=payload)
                if response.status_code in (200, 201):
                    data = response.json()
                    return MulticaIssue(
                        id=str(data.get("id", "")),
                        title=str(data.get("title", title)),
                        labels=tuple(labels),
                        assignee=data.get("assignee_id"),
                    )
                logger.warning(
                    "multica create_issue HTTP %s: %s",
                    response.status_code,
                    response.text[:200],
                )
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
        if not self.write_enabled:
            return False
        try:
            async with self._client() as client:
                response = await client.post(
                    f"/api/issues/{issue_id}/comments",
                    json={"content": body},
                )
            return response.status_code in (200, 201)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("multica add_comment failed: %s", exc)
            return False


def _priority_for(labels: list[str]) -> str:
    """Map the first recognised label onto a Multica issue priority."""
    label_set = {label.lower() for label in labels}
    for label, priority in _LABEL_PRIORITY:
        if label in label_set:
            return priority
    return _DEFAULT_PRIORITY


def _compose_description(body: str, labels: list[str]) -> str:
    """Append a labels footer to the body (Multica has no create-time labels)."""
    if not labels:
        return body
    return f"{body}\n\n— labels: {', '.join(labels)}"
