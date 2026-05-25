# Plan 5 — Regression + E2E + Migration

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Final pass before release. Run the full existing SPEC.md regression suite, the new Playwright E2E end-to-end, verify the data migration is idempotent and reversible, and check the performance budget. Update SPEC.md with the new acceptance criteria IDs. Tag `release-multi-agent-council`.

**Architecture:** No new code (mostly). Some E2E tests, a settings-health endpoint, an Alembic-style migration verification script, SPEC.md merge of new IDs.

**Spec source:** [`docs/superpowers/specs/2026-05-25-multi-agent-council-design.md`](../specs/2026-05-25-multi-agent-council-design.md) — Section 14 (Migration), Section 15 (Testing). Acceptance: `TEST-01..05`, `DATA-04..07`, all existing IDs unchanged.

---

## Task 1: SPEC.md merge

**File:** Modify `SPEC.md` to append the new acceptance criteria from `docs/superpowers/specs/...design.md`. Insert before the final References section. Use the existing `- [ ] ID-NN: description` style.

Insert new sections:
```markdown
## Agents (AGENT-*)
- [ ] AGENT-01: Each role has a canonical identifier and default BackendBinding.
... (copy from design doc §6.4)

## Debate (DEBATE-*)
- [ ] DEBATE-01: ...

## Judge (JUDGE-*)
- [ ] JUDGE-01: ...

## Memory (MEM-*)
- [ ] MEM-01: ...

## Backend providers (BACK-*)
- [ ] BACK-01: ...

## Multica (MULTICA-*)
- [ ] MULTICA-01: ...

## SSE (SSE-*)
- [ ] SSE-01: ...
```

- [ ] **Step 1:** Append all IDs verbatim from the design doc.
- [ ] **Step 2:** Commit: `git commit -m "docs(spec): merge multi-agent council acceptance criteria into SPEC.md"`

---

## Task 2: CLI health endpoint

**Files:**
- Modify: `backend/src/daily_scheduler/entrypoints/api/routes/settings.py` (existing) — add `/api/settings/health`

- [ ] **Step 1:** Failing test:
  ```python
  # backend/tests/test_settings_health.py
  from fastapi.testclient import TestClient
  from daily_scheduler.entrypoints.api.app import create_app


  def test_health_returns_cli_status() -> None:
      with TestClient(create_app()) as c:
          r = c.get("/api/settings/health")
          assert r.status_code == 200
          data = r.json()
          # Keys exist regardless of CLI availability
          assert "claude_cli" in data
          assert "codex_cli" in data
          assert "multica" in data
  ```

- [ ] **Step 2:** Add endpoint:
  ```python
  import shutil
  import asyncio


  @router.get("/health")
  async def get_health() -> dict:
      claude_path = shutil.which("claude")
      codex_path = shutil.which("codex")

      claude_v = await _version_for(claude_path) if claude_path else None
      codex_v = await _version_for(codex_path) if codex_path else None

      settings = get_settings()
      multica_up = False
      if settings.multica_base_url:
          from daily_scheduler.infrastructure.adapters.multica.http_client import (
              MulticaHTTPClient,
          )
          multica_up = await MulticaHTTPClient(base_url=settings.multica_base_url).health()

      return {
          "claude_cli": {"available": bool(claude_path), "path": claude_path, "version": claude_v},
          "codex_cli": {"available": bool(codex_path), "path": codex_path, "version": codex_v},
          "multica": {"enabled": bool(settings.multica_base_url), "up": multica_up},
      }


  async def _version_for(cli_path: str) -> str | None:
      try:
          spawn = asyncio.create_subprocess_exec  # noqa  (alias kept short)
          proc = await spawn(cli_path, "--version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
          out, _ = await asyncio.wait_for(proc.communicate(), timeout=3)
          return out.decode(errors="replace").strip().splitlines()[0] if out else None
      except Exception:
          return None
  ```

- [ ] **Step 3:** Run test → passes.

- [ ] **Step 4:** Commit: `git commit -m "feat(api): add /api/settings/health for CLI + Multica status"`

---

## Task 3: Migration verification

**Files:** Create `backend/scripts/verify_migration.py`

This is a one-shot script that runs against a fresh SQLite file and ensures all tables come up.

- [ ] **Step 1:** Create:
  ```python
  # backend/scripts/verify_migration.py
  """Verify database migration is idempotent and creates all expected tables."""
  from __future__ import annotations

  import sys
  from pathlib import Path

  from sqlalchemy import create_engine, inspect

  from daily_scheduler.database import init_database


  EXPECTED_TABLES = {
      "reports", "recommendations", "price_snapshots", "retrospectives",
      "weekly_analyses",
      # multi-agent council
      "memory_node", "memory_fts", "memory_fts_map",
      "agent_binding", "debate", "round", "speech",
  }


  def main(db_path: str = ":memory:") -> int:
      url = f"sqlite:///{db_path}" if db_path != ":memory:" else "sqlite:///:memory:"
      eng = create_engine(url)
      init_database(eng)
      init_database(eng)  # idempotency
      tables = set(inspect(eng).get_table_names())
      missing = EXPECTED_TABLES - tables
      if missing:
          print(f"MISSING TABLES: {missing}", file=sys.stderr)
          return 1
      print(f"OK — {len(tables)} tables created")
      return 0


  if __name__ == "__main__":
      sys.exit(main(*sys.argv[1:]))
  ```

- [ ] **Step 2:** Run: `cd backend && uv run python scripts/verify_migration.py` → `OK — N tables created`.

- [ ] **Step 3:** Commit: `git add backend/scripts/verify_migration.py && git commit -m "test: add migration verification script"`

---

## Task 4: Playwright E2E — full debate cycle

**File:** `frontend/tests/e2e/multi-agent-cycle.spec.ts`

Manually verify with Playwright MCP first, then encode:

- [ ] **Step 1:** Use the Playwright MCP tools to walk through:
  1. Visit `http://localhost:3000`
  2. Confirm sidebar has Agents / Debate / Memory / Multica links
  3. Click /agents → 15 cards
  4. Click `bull` → detail page; change provider to `codex`, save
  5. Click /debate → table (empty is OK)
  6. Click /memory → tree renders
  7. Click /multica → status badge visible (offline if Multica isn't up)

- [ ] **Step 2:** Encode as a Playwright spec file.

- [ ] **Step 3:** Run: `yarn playwright test`. Pass.

- [ ] **Step 4:** Commit: `git commit -m "test(e2e): Playwright full multi-agent cycle"`

---

## Task 5: Performance budget check

The spec sets daily debate end-to-end ≤ 20 minutes.

- [ ] **Step 1:** Create a synthetic timing harness:
  ```python
  # backend/tests/test_debate_perf_budget.py
  """Synthetic timing — debate engine should finish well under 20 min with mocks."""
  from __future__ import annotations

  import time
  from unittest.mock import MagicMock

  import pytest

  from daily_scheduler.application.use_cases.debate_engine import run_debate
  # Reuse the convergence router fixture
  from tests.test_graph_builder import _mock_router_for_convergence


  @pytest.mark.asyncio
  async def test_debate_completes_within_budget() -> None:
      router = _mock_router_for_convergence()
      memory = MagicMock(query_metadata=MagicMock(return_value=[]),
                        traverse_tree=MagicMock(return_value=[]))
      start = time.monotonic()
      graph = await run_debate(
          pipeline="daily", router=router, memory_store=memory,
          context={"date": "2026-05-25", "market_data": "", "screening": "",
                   "retrospective": "", "tickers": [], "regime": "neutral"},
          triggered_by="test", max_rounds=3,
      )
      elapsed = time.monotonic() - start
      assert elapsed < 5.0  # mocked LLMs return instantly; budget is for live calls
      assert graph.state.value in ("CONVERGED", "MAX_ROUNDS_DISSENT")
  ```

- [ ] **Step 2:** Run → passes.

- [ ] **Step 3:** Commit: `git commit -m "test: performance budget check (mocked path)"`

---

## Task 6: Final full regression sweep + final tag

- [ ] **Step 1:** Backend:
  ```bash
  cd backend && uv run pytest -v 2>&1 | tail -10
  cd backend && uv run ruff check src tests
  cd backend && uv run ruff format --check src tests
  cd backend && uv run pyrefly check src
  cd backend && uv run pylint src/daily_scheduler  # full src pylint, score 10.00
  ```
  Fix any drift.

- [ ] **Step 2:** Frontend:
  ```bash
  cd frontend && yarn typecheck && yarn lint && yarn oxlint
  cd frontend && yarn playwright test
  ```

- [ ] **Step 3:** Run `make test` from repo root if the project has a Makefile target.

- [ ] **Step 4:** Final tag (only on success):
  ```bash
  git tag -a release-multi-agent-council -m "Big-bang multi-agent investment council release"
  ```

- [ ] **Step 5:** No commit needed for tag — it points at the existing HEAD.

---

## Task 7: PR (only when user authorizes)

If the user explicitly authorizes a PR, push the branch and open it:

```bash
git push -u origin main  # only if user authorized push
gh pr create --title "Multi-agent investment council" --body "$(...)" 
```

This step is **not automatic** — it changes shared state (remote). Wait for explicit user authorization.

---

## Self-Review Notes

**Spec coverage:**
- `TEST-01..05` — Tasks 3, 4, 5
- `DATA-04..07` — Task 3

This plan deliberately does not introduce significant new code. It is the integration & release gate.

**Final state at completion:**
- All 5 plans implemented end-to-end
- All existing SPEC.md acceptance criteria pass
- All new acceptance criteria (~80 new IDs) pass
- Pylint 10.00/10 on backend
- ruff + pyrefly clean
- Frontend typecheck + lint + Playwright clean
- 5 tags: `plan-1-foundations`, `plan-2-debate-engine`, `plan-3-streaming-ui`, `plan-4-multica`, `release-multi-agent-council`
- One unified release commit history, no force pushes, no destructive operations
