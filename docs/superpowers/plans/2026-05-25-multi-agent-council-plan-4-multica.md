# Plan 4 — Multica Integration

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Co-deploy Multica as a Docker service, wire an HTTP client that posts events on debate failures and key milestones, accept inbound webhooks (HMAC-verified) for manual triggers, and add a `/multica` page that iframes Multica's UI.

**Architecture:** New `MulticaPort` (HTTP client + webhook verifier) with `MulticaHTTPClient` adapter (httpx). All calls are **best-effort** — failures must NOT break debates. Webhook handler is HMAC-SHA256 verified; assignment events with the right label can trigger pipeline runs. Docker-compose adds three Multica services on the same network as `daily-scheduler-backend`.

**Tech Stack:** httpx (already in deps) · sse-starlette (Plan 3) · Docker Compose · HMAC-SHA256 (stdlib).

**Spec source:** [`docs/superpowers/specs/2026-05-25-multi-agent-council-design.md`](../specs/2026-05-25-multi-agent-council-design.md) — Section 11. Acceptance: `MULTICA-01..08`, `CFG-08`.

---

## File Structure

### New backend
```
backend/src/daily_scheduler/
├── domain/ports/multica.py                          # MulticaPort + MulticaIssue
├── infrastructure/adapters/multica/
│   ├── __init__.py
│   ├── http_client.py                                # MulticaHTTPClient (httpx)
│   └── webhook_verifier.py                           # HMAC-SHA256 verifier
└── entrypoints/api/routes/
    ├── multica.py                                    # /api/multica status + iframe URL
    └── webhooks.py                                    # /webhooks/multica
```

### New frontend
- `frontend/src/app/multica/page.tsx` — iframe Multica UI + status sidebar

### Docker
- `docker-compose.yml` (new at repo root)

### Modified
- `backend/pyproject.toml` — httpx is already a dep; nothing to add
- `backend/.env.example` — `MULTICA_BASE_URL`, `MULTICA_WEBHOOK_SECRET`
- `backend/src/daily_scheduler/config.py` — `multica_base_url: str = ""`, `multica_webhook_secret: str = ""`
- `backend/src/daily_scheduler/infrastructure/adapters/council/council_news_provider.py` — call Multica on milestone events (best-effort)
- `backend/src/daily_scheduler/entrypoints/api/app.py` — register `multica` + `webhooks` routers
- `frontend/src/app/settings/page.tsx` — Multica connectivity badge
- `frontend/src/components/layout/sidebar.tsx` — `/multica` link

---

## Task 1: Config + env

- [ ] **Step 1:** Failing test — append to `backend/tests/test_config.py`:
  ```python
  def test_multica_settings_defaults() -> None:
      from daily_scheduler.config import get_settings
      s = get_settings()
      assert hasattr(s, "multica_base_url")
      assert hasattr(s, "multica_webhook_secret")
      assert s.multica_base_url == ""  # disabled by default
  ```
- [ ] **Step 2:** Run → fails.
- [ ] **Step 3:** In `Settings`, add:
  ```python
      multica_base_url: str = ""
      multica_webhook_secret: str = ""
  ```
- [ ] **Step 4:** Append to `backend/.env.example`:
  ```
  MULTICA_BASE_URL=
  MULTICA_WEBHOOK_SECRET=
  ```
- [ ] **Step 5:** Run test → passes.
- [ ] **Step 6:** Commit: `git commit -m "feat(config): add Multica base URL and webhook secret settings"`

---

## Task 2: MulticaPort + MulticaIssue + HMAC verifier

**Files:**
- Create: `backend/src/daily_scheduler/domain/ports/multica.py`
- Create: `backend/src/daily_scheduler/infrastructure/adapters/multica/__init__.py`
- Create: `backend/src/daily_scheduler/infrastructure/adapters/multica/webhook_verifier.py`
- Test: `backend/tests/test_webhook_verifier.py`

- [ ] **Step 1:** Failing test:
  ```python
  # backend/tests/test_webhook_verifier.py
  from __future__ import annotations

  import hashlib
  import hmac

  from daily_scheduler.infrastructure.adapters.multica.webhook_verifier import (
      verify_webhook,
  )


  def test_correct_signature_verifies() -> None:
      secret = "topsecret"
      body = b'{"event":"test"}'
      sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
      assert verify_webhook(body, sig, secret) is True


  def test_wrong_signature_fails() -> None:
      assert verify_webhook(b"x", "sha256=ffff", "secret") is False


  def test_malformed_signature_fails() -> None:
      assert verify_webhook(b"x", "not-an-hmac", "secret") is False


  def test_empty_secret_disables_verification() -> None:
      """When secret is empty, verifier returns False (must reject)."""
      assert verify_webhook(b"x", "sha256=anything", "") is False
  ```

- [ ] **Step 2:** Run → ModuleNotFoundError.

- [ ] **Step 3:** Create files:
  ```python
  # backend/src/daily_scheduler/domain/ports/multica.py
  """Port for Multica board interactions."""
  from __future__ import annotations

  from dataclasses import dataclass
  from typing import Protocol


  @dataclass(frozen=True, slots=True)
  class MulticaIssue:
      id: str
      title: str
      labels: tuple[str, ...]
      assignee: str | None


  class MulticaPort(Protocol):
      async def create_issue(
          self, *, title: str, body: str, labels: list[str],
      ) -> MulticaIssue | None: ...

      async def add_comment(self, *, issue_id: str, body: str) -> bool: ...

      async def health(self) -> bool: ...
  ```

  ```python
  # backend/src/daily_scheduler/infrastructure/adapters/multica/__init__.py
  """Multica integration adapters."""
  ```

  ```python
  # backend/src/daily_scheduler/infrastructure/adapters/multica/webhook_verifier.py
  """HMAC-SHA256 webhook signature verification."""
  from __future__ import annotations

  import hashlib
  import hmac


  def verify_webhook(body: bytes, signature_header: str, secret: str) -> bool:
      """Constant-time HMAC verification.

      `signature_header` format expected: 'sha256=<hex>'
      Returns False when secret is empty (no shared secret means no trust).
      """
      if not secret:
          return False
      if not signature_header.startswith("sha256="):
          return False
      provided_hex = signature_header[len("sha256="):]
      expected_hex = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
      try:
          return hmac.compare_digest(provided_hex, expected_hex)
      except (ValueError, TypeError):
          return False
  ```

- [ ] **Step 4:** Run → 4 passed.

- [ ] **Step 5:** Commit: `git commit -m "feat(multica): add MulticaPort + HMAC webhook verifier"`

---

## Task 3: MulticaHTTPClient

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/multica/http_client.py`
- Test: `backend/tests/test_multica_http_client.py`

- [ ] **Step 1:** Failing test using httpx MockTransport:
  ```python
  # backend/tests/test_multica_http_client.py
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
          return httpx.Response(201, json={"id": "i1", "title": body["title"], "labels": body["labels"], "assignee": None})
      client = MulticaHTTPClient(base_url="http://mc", transport=_transport(handler), timeout_s=2)
      issue = await client.create_issue(title="t", body="b", labels=["dissent"])
      assert issue is not None
      assert issue.id == "i1"


  @pytest.mark.asyncio
  async def test_create_issue_returns_none_on_http_error() -> None:
      def handler(req): return httpx.Response(500)
      client = MulticaHTTPClient(base_url="http://mc", transport=_transport(handler), timeout_s=2)
      assert (await client.create_issue(title="t", body="b", labels=[])) is None


  @pytest.mark.asyncio
  async def test_health_check() -> None:
      def handler(req): return httpx.Response(200, json={"status": "ok"})
      client = MulticaHTTPClient(base_url="http://mc", transport=_transport(handler), timeout_s=2)
      assert await client.health() is True


  @pytest.mark.asyncio
  async def test_disabled_when_base_url_empty() -> None:
      client = MulticaHTTPClient(base_url="", transport=None, timeout_s=2)
      assert await client.health() is False
      assert (await client.create_issue(title="t", body="b", labels=[])) is None
  ```

- [ ] **Step 2:** Run → ModuleNotFoundError.

- [ ] **Step 3:** Create:
  ```python
  # backend/src/daily_scheduler/infrastructure/adapters/multica/http_client.py
  """MulticaHTTPClient — best-effort HTTP integration with Multica."""
  from __future__ import annotations

  import logging

  import httpx

  from daily_scheduler.constants import MULTICA_HTTP_TIMEOUT_S, MULTICA_RETRY_COUNT
  from daily_scheduler.domain.ports.multica import MulticaIssue, MulticaPort

  logger = logging.getLogger(__name__)


  class MulticaHTTPClient(MulticaPort):
      def __init__(
          self,
          base_url: str,
          *,
          transport: httpx.BaseTransport | None = None,
          timeout_s: int = MULTICA_HTTP_TIMEOUT_S,
      ) -> None:
          self._base_url = base_url.rstrip("/")
          self._transport = transport
          self._timeout_s = timeout_s

      @property
      def enabled(self) -> bool:
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
              async with self._client() as c:
                  r = await c.get("/api/health")
              return r.status_code == 200
          except Exception as e:  # noqa: BLE001
              logger.warning("multica health failed: %s", e)
              return False

      async def create_issue(
          self, *, title: str, body: str, labels: list[str],
      ) -> MulticaIssue | None:
          if not self.enabled:
              return None
          payload = {"title": title, "body": body, "labels": labels}
          for attempt in range(MULTICA_RETRY_COUNT + 1):
              try:
                  async with self._client() as c:
                      r = await c.post("/api/issues", json=payload)
                  if r.status_code in (200, 201):
                      data = r.json()
                      return MulticaIssue(
                          id=str(data.get("id", "")),
                          title=str(data.get("title", title)),
                          labels=tuple(data.get("labels", labels) or []),
                          assignee=data.get("assignee"),
                      )
                  logger.warning("multica create_issue HTTP %s", r.status_code)
              except Exception as e:  # noqa: BLE001
                  logger.warning("multica create_issue attempt %d failed: %s", attempt + 1, e)
                  if attempt == MULTICA_RETRY_COUNT:
                      break
          return None

      async def add_comment(self, *, issue_id: str, body: str) -> bool:
          if not self.enabled:
              return False
          try:
              async with self._client() as c:
                  r = await c.post(f"/api/issues/{issue_id}/comments", json={"body": body})
              return r.status_code in (200, 201)
          except Exception as e:  # noqa: BLE001
              logger.warning("multica add_comment failed: %s", e)
              return False
  ```

- [ ] **Step 4:** Run → 4 passed.

- [ ] **Step 5:** Commit: `git commit -m "feat(multica): add MulticaHTTPClient (best-effort httpx wrapper)"`

---

## Task 4: Outbound integration in CouncilNewsProvider

**Files:** Modify `backend/src/daily_scheduler/infrastructure/adapters/council/council_news_provider.py`

- [ ] **Step 1:** Add `multica: MulticaPort | None = None` to `__init__`.
- [ ] **Step 2:** After `run_debate` returns, if `multica is not None` and `graph.state in (DebateState.MAX_ROUNDS_DISSENT, DebateState.FAILED)`, call:
  ```python
  await self._multica.create_issue(
      title=f"[{pipeline}] {graph.state.value} {graph.id[:8]}",
      body=f"Debate did not converge.\nrounds: {len(graph.rounds)}\nerror: {graph.error or '-'}",
      labels=["dissent" if graph.state == DebateState.MAX_ROUNDS_DISSENT else "infra"],
  )
  ```
  Wrap the call in `try/except` — never let it raise out.
- [ ] **Step 3:** Wire into `get_news_provider` factory in `dependencies.py`:
  ```python
  settings = get_settings()
  multica: MulticaPort | None = None
  if settings.multica_base_url:
      multica = MulticaHTTPClient(base_url=settings.multica_base_url)
  return CouncilNewsProvider(router=router, memory_store=memory_store,
                             debate_repo=..., multica=multica)
  ```
- [ ] **Step 4:** Add test `backend/tests/test_council_multica_integration.py`:
  ```python
  """Council should post to Multica when a debate fails to converge."""
  from __future__ import annotations

  from unittest.mock import AsyncMock, MagicMock

  import pytest

  from daily_scheduler.domain.entities.debate import DebateState
  from daily_scheduler.infrastructure.adapters.council.council_news_provider import (
      CouncilNewsProvider,
  )


  @pytest.mark.asyncio
  async def test_multica_called_when_debate_fails(monkeypatch) -> None:
      async def fake_run_debate(**kwargs):
          from daily_scheduler.domain.entities.debate import DebateGraph, Verdict
          from datetime import datetime
          return DebateGraph(
              id="d1", pipeline="daily", state=DebateState.MAX_ROUNDS_DISSENT,
              rounds=[], analyst_reports=[], verdict=None,
              started_at=datetime.now(), ended_at=datetime.now(),
              triggered_by="test", error=None,
          )
      monkeypatch.setattr(
          "daily_scheduler.application.use_cases.debate_engine.run_debate",
          fake_run_debate,
      )
      multica = MagicMock()
      multica.create_issue = AsyncMock(return_value=None)
      provider = CouncilNewsProvider(
          router=MagicMock(), memory_store=MagicMock(),
          multica=multica,
      )
      text, _ = await provider._run_pipeline("daily", {"date": "2026-05-25"})
      multica.create_issue.assert_awaited_once()
  ```
- [ ] **Step 5:** Run test → passes (after provider mod).
- [ ] **Step 6:** Commit: `git commit -m "feat(council): post Multica issue on debate non-convergence (best-effort)"`

---

## Task 5: Webhook endpoint

**Files:**
- Create: `backend/src/daily_scheduler/entrypoints/api/routes/webhooks.py`
- Test: `backend/tests/test_webhooks_endpoint.py`

- [ ] **Step 1:** Failing test:
  ```python
  from __future__ import annotations

  import hashlib
  import hmac
  import json

  from fastapi.testclient import TestClient

  from daily_scheduler.entrypoints.api.app import create_app


  def _sign(body: bytes, secret: str) -> str:
      return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


  def test_webhook_rejects_missing_signature(monkeypatch) -> None:
      monkeypatch.setenv("MULTICA_WEBHOOK_SECRET", "topsecret")
      with TestClient(create_app()) as c:
          r = c.post("/webhooks/multica", json={"event": "issue.assigned"})
          assert r.status_code == 401


  def test_webhook_accepts_valid_signature(monkeypatch) -> None:
      monkeypatch.setenv("MULTICA_WEBHOOK_SECRET", "topsecret")
      body = json.dumps({"event": "issue.assigned", "issue": {"id": "i1", "labels": [], "title": "test"}}).encode()
      with TestClient(create_app()) as c:
          r = c.post(
              "/webhooks/multica", content=body,
              headers={"X-Multica-Signature": _sign(body, "topsecret"),
                       "Content-Type": "application/json"},
          )
          assert r.status_code == 200
  ```

- [ ] **Step 2:** Run → 404 (route missing).

- [ ] **Step 3:** Create:
  ```python
  # backend/src/daily_scheduler/entrypoints/api/routes/webhooks.py
  """Inbound webhooks from Multica."""
  from __future__ import annotations

  import logging

  from fastapi import APIRouter, Header, HTTPException, Request

  from daily_scheduler.config import get_settings
  from daily_scheduler.infrastructure.adapters.multica.webhook_verifier import (
      verify_webhook,
  )

  logger = logging.getLogger(__name__)
  router = APIRouter(prefix="/webhooks", tags=["webhooks"])


  @router.post("/multica")
  async def multica_webhook(
      request: Request,
      x_multica_signature: str = Header(default=""),
  ) -> dict:
      settings = get_settings()
      body = await request.body()
      if not verify_webhook(body, x_multica_signature, settings.multica_webhook_secret):
          logger.warning("multica webhook signature mismatch (body_len=%d)", len(body))
          raise HTTPException(401, "invalid signature")
      try:
          payload = (await request.json()) if body else {}
      except Exception:
          payload = {}
      event = payload.get("event")
      logger.info("multica webhook event=%s", event)

      # Manual trigger pattern: issue.assigned + label 'manual-trigger' + title 'rerun {pipeline}'
      if event == "issue.assigned":
          issue = payload.get("issue", {})
          labels = set(issue.get("labels", []))
          title = str(issue.get("title", ""))
          if "manual-trigger" in labels and title.startswith("rerun "):
              pipeline = title.removeprefix("rerun ").strip()
              if pipeline in ("daily", "news", "global-news", "weekly"):
                  logger.info("multica triggered pipeline=%s", pipeline)
                  # Defer to the existing /api/pipeline/run mechanism if needed;
                  # for Plan 4 we just acknowledge.
                  return {"ok": True, "triggered": pipeline}

      return {"ok": True}
  ```

- [ ] **Step 4:** Register in `app.py`. Run test → 2 passed.

- [ ] **Step 5:** Commit: `git commit -m "feat(api): add HMAC-verified Multica webhook endpoint"`

---

## Task 6: /api/multica status + /multica frontend page

**Files:**
- Create: `backend/src/daily_scheduler/entrypoints/api/routes/multica.py`
- Create: `frontend/src/app/multica/page.tsx`

- [ ] **Step 1:** Backend route:
  ```python
  # backend/src/daily_scheduler/entrypoints/api/routes/multica.py
  """Status endpoint for the /multica UI page."""
  from __future__ import annotations

  from fastapi import APIRouter

  from daily_scheduler.config import get_settings
  from daily_scheduler.infrastructure.adapters.multica.http_client import (
      MulticaHTTPClient,
  )

  router = APIRouter(prefix="/api/multica", tags=["multica"])


  @router.get("/status")
  async def status() -> dict:
      settings = get_settings()
      if not settings.multica_base_url:
          return {"enabled": False, "up": False, "url": None}
      client = MulticaHTTPClient(base_url=settings.multica_base_url)
      up = await client.health()
      return {"enabled": True, "up": up, "url": settings.multica_base_url}
  ```

- [ ] **Step 2:** Register router.

- [ ] **Step 3:** Frontend:
  ```tsx
  // frontend/src/app/multica/page.tsx
  "use client";
  import { useQuery } from "@tanstack/react-query";
  import { api } from "@/lib/api-client";

  export default function MulticaPage() {
    const { data } = useQuery({
      queryKey: ["multica-status"],
      queryFn: () => api.get<{enabled: boolean; up: boolean; url: string | null}>("/api/multica/status"),
      refetchInterval: 15000,
    });

    if (!data) return <div className="p-8">Loading…</div>;
    if (!data.enabled) {
      return (
        <main className="p-8 space-y-3">
          <h1 className="text-2xl font-semibold">Multica</h1>
          <p className="text-sm opacity-70">Multica integration is disabled. Set MULTICA_BASE_URL to enable.</p>
        </main>
      );
    }

    return (
      <main className="p-0 flex flex-col h-[calc(100vh-4rem)]">
        <header className="p-4 border-b flex items-center gap-3">
          <h1 className="text-lg font-semibold">Multica</h1>
          <span className={"text-xs px-2 py-0.5 rounded " + (data.up ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800")}>
            {data.up ? "connected" : "offline"}
          </span>
        </header>
        {data.up && data.url ? (
          <iframe src={data.url} className="flex-1 w-full" title="Multica board" />
        ) : (
          <div className="p-8 text-sm opacity-70">
            Multica is configured but unreachable at {data.url}. Check docker-compose status.
          </div>
        )}
      </main>
    );
  }
  ```

- [ ] **Step 4:** Add `/multica` to sidebar.

- [ ] **Step 5:** Test the page renders (with stub backend returning `enabled: false` is fine for unit-level).

- [ ] **Step 6:** Commit: `git commit -m "feat: add /multica iframe page + status endpoint"`

---

## Task 7: docker-compose.yml

**Files:** Create `docker-compose.yml` at repo root

- [ ] **Step 1:** Create:
  ```yaml
  # docker-compose.yml — multi-agent council co-deployment
  services:
    multica-postgres:
      image: postgres:17
      environment:
        POSTGRES_DB: multica
        POSTGRES_USER: multica
        POSTGRES_PASSWORD: ${MULTICA_DB_PASSWORD:-multica_local_dev}
      volumes:
        - multica_pg_data:/var/lib/postgresql/data
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U multica -d multica"]
        interval: 5s
        timeout: 5s
        retries: 10

    multica-backend:
      image: ghcr.io/multica-ai/multica-backend:latest
      depends_on:
        multica-postgres:
          condition: service_healthy
      environment:
        MULTICA_DATABASE_URL: postgres://multica:${MULTICA_DB_PASSWORD:-multica_local_dev}@multica-postgres:5432/multica
        MULTICA_WEBHOOK_URL: http://daily-scheduler-backend:8000/webhooks/multica
        MULTICA_WEBHOOK_SECRET: ${MULTICA_WEBHOOK_SECRET:-changeme}
      ports:
        - "8080:8080"

    multica-frontend:
      image: ghcr.io/multica-ai/multica-frontend:latest
      depends_on:
        - multica-backend
      environment:
        MULTICA_BACKEND_URL: http://multica-backend:8080
      ports:
        - "3001:3000"

    daily-scheduler-backend:
      build:
        context: ./backend
        dockerfile: Dockerfile
      environment:
        MULTICA_BASE_URL: http://multica-backend:8080
        MULTICA_WEBHOOK_SECRET: ${MULTICA_WEBHOOK_SECRET:-changeme}
        DATABASE_URL: sqlite:////app/data/daily_scheduler.db
      volumes:
        - ./backend:/app
        - ./data:/app/data
      ports:
        - "8000:8000"
      depends_on:
        - multica-backend

  volumes:
    multica_pg_data:
  ```

- [ ] **Step 2:** Create a minimal `backend/Dockerfile`:
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY pyproject.toml uv.lock ./
  RUN pip install uv && uv sync --extra dev --frozen
  COPY . .
  EXPOSE 8000
  CMD ["uv", "run", "uvicorn", "daily_scheduler.entrypoints.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
  ```

- [ ] **Step 3:** Verify with `docker compose config` (lint only, no actual run required for Plan 4 commit).

- [ ] **Step 4:** Commit: `git commit -m "chore: add docker-compose.yml for Multica + daily-scheduler co-deployment"`

---

## Task 8: Settings page extension + sidebar nav

- [ ] **Step 1:** Modify `frontend/src/app/settings/page.tsx`:
  - Add a "Multi-agent operations" card that fetches `/api/multica/status` (use React Query)
  - Show `enabled` badge, `up` indicator with last-checked timestamp

- [ ] **Step 2:** Add `/multica` link to `frontend/src/components/layout/sidebar.tsx`.

- [ ] **Step 3:** `yarn typecheck && yarn lint` clean.

- [ ] **Step 4:** Commit: `git commit -m "feat(frontend): wire Multica into settings + sidebar"`

---

## Task 9: Full regression + lint + tag

- [ ] **Step 1:** Backend full pytest → all green.
- [ ] **Step 2:** Backend: ruff, format, pyrefly, pylint on new modules (`infrastructure/adapters/multica`, `entrypoints/api/routes/multica.py`, `entrypoints/api/routes/webhooks.py`, `domain/ports/multica.py`). Pylint 10.00/10.
- [ ] **Step 3:** Frontend: typecheck, lint, oxlint clean.
- [ ] **Step 4:** Tag: `git tag -a plan-4-multica -m "Plan 4 complete: Multica integration"`.

---

## Self-Review Notes

**Spec coverage:**
- `MULTICA-01..08` — Tasks 2-8
- `CFG-08` — Task 1 (empty base URL gracefully disables)

**Risk:**
- Multica's HTTP API is not officially documented for outside consumers. The endpoints `/api/issues`, `/api/issues/{id}/comments`, `/api/health` are educated guesses from the README. If Multica's actual paths differ, update `http_client.py` and the test fixtures. The adapter layer is thin and easy to adjust.

**Out of scope (Plan 5):**
- Full Playwright E2E that boots both stacks
- Performance budget verification
- Final migration verification
