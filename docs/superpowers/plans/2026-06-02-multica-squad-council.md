# Multica-Squad Council + Report-Only — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the daily trading report through the Multica "Investment Council" squad (agents execute inside Multica), with the in-process council as a fallback, and remove the two news-only briefing pipelines.

**Architecture:** A new `MulticaSquadReportProvider` implements the existing `generate_daily_report` seam. It creates a Multica issue assigned to the Investment Council squad, polls until quiescence/terminal status, and extracts the leader's final fenced-JSON report. On any failure it delegates to the retained in-process `CouncilReportProvider`. The two news pipelines are deleted end-to-end.

**Tech Stack:** Python 3 + FastAPI + uv, httpx, SQLAlchemy/SQLite, Multica self-host API (`/api/issues`, `/comments`, `/runs`), pytest, ruff/pyrefly/pylint/mypy.

**Design doc:** `docs/superpowers/specs/2026-06-02-multica-squad-council-design.md`

**Decisions locked:** weekly retrospective stays in-process; `make dev` only warns (no auto daemon install) when the squad is unresolvable and falls back.

---

## File Structure

**Part A — remove news (delete/modify):**
- Delete: `scheduler/install-news.sh`, `install-news-linux.sh`, `install-global-news.sh`, `install-global-news-linux.sh`, `run_news.sh`, `run_global_news.sh`, `com.dailyscheduler.news.plist`, `com.dailyscheduler.global-news.plist`
- Delete: `backend/src/daily_scheduler/application/use_cases/run_news_pipeline.py`
- Modify: `entrypoints/cli/commands.py` (drop `run-news`, `run-global-news`)
- Modify: `domain/ports/news_provider.py` (drop 2 news methods)
- Modify: `infrastructure/adapters/council/council_news_provider.py` → rename file/class to `council_report_provider.py` / `CouncilReportProvider`; drop news methods
- Modify: `infrastructure/dependencies.py` (drop `get_news_pipeline`, `get_global_news_pipeline`; rename `get_news_provider`→`get_report_provider`)
- Modify: `Makefile` (drop `news-scheduler-*`, `global-news-scheduler-*`, `run-news`, `run-global-news`; clean `dev` trap)
- Modify: `backend/tests/test_council_news_provider.py`, `test_graph_builder.py` (drop news cases)
- Modify: `README.md`, `SPEC.md`, `constants.py` (`NEWS_SCHEDULE_TIME`), frontend report-type labels if any

**Part B — Multica squad (create/modify):**
- Modify: `domain/ports/multica.py` (new dataclasses + port methods)
- Modify: `infrastructure/adapters/multica/http_client.py` (implement new methods + assignee + backoff)
- Create: `infrastructure/adapters/council/multica_squad_report_provider.py`
- Create: `infrastructure/adapters/council/report_envelope.py` (extract fenced JSON)
- Modify: `infrastructure/dependencies.py` (`get_report_provider` returns squad provider w/ fallback)
- Modify: `config.py` (`multica_squad_id`), `constants.py` (squad name, poll/timeout/grace, backoff)
- Modify: `scripts/multica-register-agents.py` (strict report-JSON skill + member→leader @mention instruction)
- Create: `backend/tests/test_multica_squad_report_provider.py`, `test_report_envelope.py`
- Modify: `backend/tests/test_multica_http_client.py` (new methods)
- Create: `backend/tests/test_multica_squad_integration.py` (`--integration`)

---

## PART A — Remove the news briefings

### Task A1: Delete news scheduler assets

- [ ] **Step 1: Delete the files**

```bash
cd /Users/bany1111/local-workspace/daily-scheduler
git rm scheduler/install-news.sh scheduler/install-news-linux.sh \
       scheduler/install-global-news.sh scheduler/install-global-news-linux.sh \
       scheduler/run_news.sh scheduler/run_global_news.sh \
       scheduler/com.dailyscheduler.news.plist scheduler/com.dailyscheduler.global-news.plist
```

- [ ] **Step 2: Unload any installed launchd jobs (best-effort, local)**

```bash
launchctl bootout gui/$(id -u)/com.dailyscheduler.news 2>/dev/null || true
launchctl bootout gui/$(id -u)/com.dailyscheduler.global-news 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.dailyscheduler.news.plist" "$HOME/Library/LaunchAgents/com.dailyscheduler.global-news.plist"
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore(scheduler): remove news + global-news scheduler assets"
```

### Task A2: Strip news targets from the Makefile

- [ ] **Step 1:** In `Makefile`, remove from `.PHONY` and delete the target blocks:
`run-news`, `run-global-news`, `news-scheduler-install/-uninstall/-status/-start/-stop`,
`global-news-scheduler-install/-uninstall/-status/-start/-stop`, and the `-linux` variants.
- [ ] **Step 2:** In the `dev:` and `dev-linux:` recipes, delete the lines that call
`scheduler/install-news.sh`, `scheduler/install-global-news.sh` (and `-linux`) and the
matching `launchctl bootout … com.dailyscheduler.news/.global-news` / crontab `grep -v`
cleanup lines in the trap. Leave the daily `report` scheduler intact.
- [ ] **Step 3: Verify** `make help` lists no `news`/`global-news` targets:
`make help 2>/dev/null | grep -iE "news" || echo "clean"` → Expected: `clean`
- [ ] **Step 4: Commit** `git commit -am "chore(make): drop news + global-news targets"`

### Task A3: Remove the news CLI commands

**Files:** Modify `backend/src/daily_scheduler/entrypoints/cli/commands.py`

- [ ] **Step 1:** Delete the entire `@app.command(name="run-news")` function `run_news` and
the entire `@app.command(name="run-global-news")` function `run_global_news`.
- [ ] **Step 2: Verify they are gone**

Run: `cd backend && uv run daily-scheduler --help`
Expected: command list shows `run`, `serve`, `init-db`, `check` — NO `run-news`/`run-global-news`.

- [ ] **Step 3: Commit** `git commit -am "feat(cli): remove news briefing commands"`

### Task A4: Drop news methods from the port + provider

**Files:** Modify `domain/ports/news_provider.py`, rename `council_news_provider.py`.

- [ ] **Step 1:** In `news_provider.py` delete the `generate_news_briefing` and
`generate_global_news_briefing` abstract methods (keep `generate_daily_report`,
`generate_weekly_report`).
- [ ] **Step 2:** `git mv backend/src/daily_scheduler/infrastructure/adapters/council/council_news_provider.py backend/src/daily_scheduler/infrastructure/adapters/council/council_report_provider.py`
- [ ] **Step 3:** In that file rename class `CouncilNewsProvider` → `CouncilReportProvider`;
delete methods `generate_news_briefing` and `generate_global_news_briefing`. Keep
`generate_daily_report`, `generate_weekly_report`, `_run_pipeline`, `_persist_debate`,
`_notify_multica_on_failure`, helpers.
- [ ] **Step 4:** Update imports/usages: `grep -rn "CouncilNewsProvider\|council_news_provider" backend/src backend/tests` and replace with the new names.
- [ ] **Step 5: Run the provider tests** (updated in A6 — for now expect failures from removed methods; that's fine until A6).
- [ ] **Step 6: Commit** `git commit -am "refactor(council): CouncilReportProvider, drop news methods"`

### Task A5: Remove news pipeline use case + dependency wiring

**Files:** Delete `application/use_cases/run_news_pipeline.py`; modify `infrastructure/dependencies.py`.

- [ ] **Step 1:** `git rm backend/src/daily_scheduler/application/use_cases/run_news_pipeline.py`
- [ ] **Step 2:** In `dependencies.py` delete `get_news_pipeline` and `get_global_news_pipeline`
and the `RunNewsBriefingPipeline` import. Rename `get_news_provider` → `get_report_provider`
and update its return type to `CouncilReportProvider` (Part B re-wires it). Update the two
call sites in `get_daily_pipeline` / `get_weekly_pipeline` (`news=get_report_provider(...)`).
- [ ] **Step 3:** `grep -rn "RunNewsBriefingPipeline\|get_news_pipeline\|get_global_news_pipeline\|get_news_provider" backend/src` → Expected: no matches.
- [ ] **Step 4: Commit** `git commit -am "feat(pipeline): remove news/global-news pipelines + wiring"`

### Task A6: Update tests + docs for the removal; green `make test`

**Files:** `backend/tests/test_council_news_provider.py`, `test_graph_builder.py`, `README.md`, `SPEC.md`, `constants.py`.

- [ ] **Step 1:** Rename `test_council_news_provider.py` → `test_council_report_provider.py`;
delete tests that call `generate_news_briefing`/`generate_global_news_briefing`; keep daily/weekly.
- [ ] **Step 2:** In `test_graph_builder.py` keep `is_news_pipeline`/`is_weekly_pipeline` unit
coverage only if those helpers remain used by the debate engine; if the `news`/`global-news`
branches are now dead, delete the engine branches (`_run_news_flow`, `is_news_pipeline`) and
their tests. (Check `grep -rn "is_news_pipeline\|_run_news_flow" backend/src`.)
- [ ] **Step 3:** Remove `NEWS_SCHEDULE_TIME` from `constants.py` and its `.env.example`
entry; remove news sections from `README.md` / `SPEC.md`.
- [ ] **Step 4: Run** `make test` → Expected: all pass (pytest, pyrefly, pylint 10.00, frontend typecheck/oxlint). Fix any fallout.
- [ ] **Step 5: Commit** `git commit -am "test+docs: drop news coverage; green suite"`

---

## PART B — Run the daily report through the Multica squad

### Task B1: Extend the MulticaPort with squad + read operations

**Files:** Modify `domain/ports/multica.py`. Test: `backend/tests/test_multica_port_types.py` (new, trivial).

- [ ] **Step 1: Write the dataclasses + protocol methods**

```python
# domain/ports/multica.py — add alongside MulticaIssue
@dataclass(frozen=True, slots=True)
class MulticaIssueState:
    """Lightweight issue status snapshot."""
    id: str
    status: str  # backlog|todo|in_progress|in_review|done|blocked|cancelled

@dataclass(frozen=True, slots=True)
class MulticaComment:
    id: str
    author_type: str  # "agent" | "member"
    author_id: str
    content: str

@dataclass(frozen=True, slots=True)
class MulticaRun:
    id: str
    agent_id: str
    kind: str       # "direct" | "comment"
    status: str     # queued|running|completed|failed
```

Add to the `MulticaPort` Protocol (all best-effort; disabled impls return None/[]):

```python
    async def create_issue(
        self, *, title: str, body: str, labels: list[str],
        assignee_id: str | None = None,
    ) -> MulticaIssue | None: ...

    async def get_issue(self, *, issue_id: str) -> MulticaIssueState | None: ...
    async def list_comments(self, *, issue_id: str) -> list[MulticaComment]: ...
    async def list_runs(self, *, issue_id: str) -> list[MulticaRun]: ...
```

- [ ] **Step 2: Write a failing import test**

```python
# backend/tests/test_multica_port_types.py
from daily_scheduler.domain.ports.multica import (
    MulticaIssueState, MulticaComment, MulticaRun,
)

def test_dataclasses_exist():
    s = MulticaIssueState(id="1", status="todo")
    assert s.status == "todo"
```

- [ ] **Step 3: Run** `cd backend && uv run pytest tests/test_multica_port_types.py -q` → Expected: PASS.
- [ ] **Step 4: Commit** `git commit -am "feat(port): extend MulticaPort with squad+read ops"`

### Task B2: Implement the new MulticaHTTPClient methods (assignee + reads + backoff)

**Files:** Modify `infrastructure/adapters/multica/http_client.py`. Test: `backend/tests/test_multica_http_client.py`.

- [ ] **Step 1: Write failing tests** using `httpx.MockTransport` that assert:
  - `create_issue(..., assignee_id="sq1")` POSTs `assignee_type:"squad", assignee_id:"sq1"` in the body.
  - `get_issue` GETs `/api/issues/{id}` and maps `status`.
  - `list_comments` GETs `/api/issues/{id}/comments` and maps `author_type`/`content`.
  - `list_runs` GETs `/api/issues/{id}/runs` and maps `kind`/`status`.

```python
def test_create_issue_with_squad_assignee():
    seen = {}
    def handler(req):
        import json
        seen.update(json.loads(req.content))
        return httpx.Response(201, json={"id": "i1", "title": "t", "assignee_id": "sq1"})
    tr = httpx.MockTransport(handler)
    c = MulticaHTTPClient("http://x", api_token="tok", workspace_id="ws", transport=tr)
    issue = asyncio.run(c.create_issue(title="t", body="b", labels=[], assignee_id="sq1"))
    assert issue and issue.id == "i1"
    assert seen["assignee_type"] == "squad" and seen["assignee_id"] == "sq1"
```

- [ ] **Step 2: Run** the new tests → Expected: FAIL (assignee not sent / methods missing).
- [ ] **Step 3: Implement.** In `create_issue` add `assignee_id` param; when set, add
`payload["assignee_type"] = "squad"; payload["assignee_id"] = assignee_id`. Add a backoff
`await asyncio.sleep(MULTICA_BACKOFF_BASE_S * (attempt + 1))` between retries and return
`None` immediately on 4xx (no retry). Add:

```python
    async def get_issue(self, *, issue_id: str) -> MulticaIssueState | None:
        if not self.write_enabled:
            return None
        try:
            async with self._client() as client:
                r = await client.get(f"/api/issues/{issue_id}")
            if r.status_code == 200:
                d = r.json()
                return MulticaIssueState(id=str(d.get("id", issue_id)), status=str(d.get("status", "")))
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("multica get_issue failed: %s", exc)
        return None

    async def list_comments(self, *, issue_id: str) -> list[MulticaComment]:
        if not self.write_enabled:
            return []
        try:
            async with self._client() as client:
                r = await client.get(f"/api/issues/{issue_id}/comments")
            if r.status_code == 200:
                data = r.json()
                items = data if isinstance(data, list) else data.get("comments", [])
                return [
                    MulticaComment(
                        id=str(c.get("id", "")),
                        author_type=str(c.get("author_type", "")),
                        author_id=str(c.get("author_id", "")),
                        content=str(c.get("content") or c.get("body") or ""),
                    )
                    for c in items or []
                ]
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("multica list_comments failed: %s", exc)
        return []

    async def list_runs(self, *, issue_id: str) -> list[MulticaRun]:
        if not self.write_enabled:
            return []
        try:
            async with self._client() as client:
                r = await client.get(f"/api/issues/{issue_id}/runs")
            if r.status_code == 200:
                data = r.json()
                items = data if isinstance(data, list) else data.get("runs", [])
                return [
                    MulticaRun(
                        id=str(x.get("id", "")), agent_id=str(x.get("agent_id", "")),
                        kind=str(x.get("kind", "")), status=str(x.get("status", "")),
                    )
                    for x in items or []
                ]
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("multica list_runs failed: %s", exc)
        return []
```

Add `MULTICA_BACKOFF_BASE_S = 2` to `constants.py` and import it.

- [ ] **Step 4: Run** `cd backend && uv run pytest tests/test_multica_http_client.py -q` → Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat(multica): squad assignee + issue/comment/run reads + backoff"`

### Task B3: Report-envelope extraction helper

**Files:** Create `infrastructure/adapters/council/report_envelope.py`. Test: `backend/tests/test_report_envelope.py`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_report_envelope.py
from daily_scheduler.infrastructure.adapters.council.report_envelope import extract_report_json

def test_extracts_fenced_json():
    text = "Here is the report:\n```json\n{\"market_summary\": \"ok\"}\n```\nthanks"
    assert extract_report_json(text) == '{"market_summary": "ok"}'

def test_returns_none_without_valid_json():
    assert extract_report_json("no json here") is None

def test_prefers_last_valid_block():
    text = "```json\n{\"a\":1}\n```\n```json\n{\"market_summary\":\"final\"}\n```"
    assert '"final"' in (extract_report_json(text) or "")
```

- [ ] **Step 2: Run** → Expected: FAIL (module missing).
- [ ] **Step 3: Implement**

```python
"""Extract the final report JSON envelope from a squad leader's comment."""
from __future__ import annotations
import json
import re

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

def extract_report_json(text: str) -> str | None:
    """Return the last fenced JSON object that parses, else any parseable {...}."""
    candidates = _FENCE.findall(text or "")
    for block in reversed(candidates):
        try:
            json.loads(block)
            return block
        except (ValueError, TypeError):
            continue
    # Fallback: a bare top-level object
    start, end = (text or "").find("{"), (text or "").rfind("}")
    if 0 <= start < end:
        snippet = text[start : end + 1]
        try:
            json.loads(snippet)
            return snippet
        except (ValueError, TypeError):
            return None
    return None
```

- [ ] **Step 4: Run** `cd backend && uv run pytest tests/test_report_envelope.py -q` → Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat(council): report JSON envelope extractor"`

### Task B4: MulticaSquadReportProvider — happy path (issue → poll → extract)

**Files:** Create `infrastructure/adapters/council/multica_squad_report_provider.py`. Test: `backend/tests/test_multica_squad_report_provider.py`.

- [ ] **Step 1: Write failing test** with a fake `MulticaPort` scripting create→runs→comments→status:

```python
# backend/tests/test_multica_squad_report_provider.py
import asyncio
from datetime import date
from daily_scheduler.domain.ports.multica import (
    MulticaIssue, MulticaIssueState, MulticaComment, MulticaRun,
)
from daily_scheduler.infrastructure.adapters.council.multica_squad_report_provider import (
    MulticaSquadReportProvider,
)

class FakeMultica:
    def __init__(self): self.created = None
    async def health(self): return True
    async def create_issue(self, *, title, body, labels, assignee_id=None):
        self.created = (title, assignee_id); return MulticaIssue(id="i1", title=title, labels=tuple(labels), assignee=None)
    async def get_issue(self, *, issue_id): return MulticaIssueState(id=issue_id, status="in_review")
    async def list_runs(self, *, issue_id):
        return [MulticaRun(id="r1", agent_id="pm", kind="direct", status="completed"),
                MulticaRun(id="r2", agent_id="an", kind="comment", status="completed")]
    async def list_comments(self, *, issue_id):
        return [MulticaComment(id="c1", author_type="agent", author_id="pm",
                content='final: ```json\n{"market_summary":"S","report_date":"2026-06-02"}\n```')]
    async def add_comment(self, **k): return True

class BoomFallback:
    def generate_daily_report(self, *a, **k): raise AssertionError("fallback must not run on success")

def test_happy_path_returns_extracted_report(monkeypatch):
    p = MulticaSquadReportProvider(multica=FakeMultica(), squad_id="sq1",
        fallback=BoomFallback(), poll_interval_s=0, timeout_s=5, quiescence_grace_s=0)
    raw, elapsed = p.generate_daily_report(date(2026, 6, 2), "retro")
    assert '"market_summary": "S"' in raw.replace(" ", "") or '"market_summary":"S"' in raw
    assert p._multica.created[1] == "sq1"
```

- [ ] **Step 2: Run** → Expected: FAIL (module missing).
- [ ] **Step 3: Implement the provider** (sync `generate_*` wrap async via the same
`_run_sync` helper used by `CouncilReportProvider` — import or duplicate minimally):

```python
"""MulticaSquadReportProvider — runs the daily report via the Multica squad."""
from __future__ import annotations
import asyncio, logging, time
from datetime import date
from typing import Protocol

from daily_scheduler.domain.ports.multica import MulticaPort
from daily_scheduler.domain.ports.news_provider import NewsProviderPort
from daily_scheduler.infrastructure.adapters.council.council_report_provider import _run_sync
from daily_scheduler.infrastructure.adapters.council.report_envelope import extract_report_json
from daily_scheduler.infrastructure.adapters.claude.parser import parse_report_content

logger = logging.getLogger(__name__)
_TERMINAL = {"in_review", "done"}

class _Fallback(Protocol):
    def generate_daily_report(self, report_date: date, retrospective_context: str,
        weekly_lessons: str = "", market_data: str = "", screening_data: str = "") -> tuple[str, float]: ...
    def generate_weekly_report(self, report_date: date, weekly_stats: str,
        detailed_performance: str, closed_rationales: str = "") -> tuple[str, float]: ...

class MulticaSquadReportProvider(NewsProviderPort):
    def __init__(self, *, multica: MulticaPort, squad_id: str, fallback: _Fallback,
                 poll_interval_s: int, timeout_s: int, quiescence_grace_s: int) -> None:
        self._multica = multica
        self._squad_id = squad_id
        self._fallback = fallback
        self._poll = poll_interval_s
        self._timeout = timeout_s
        self._grace = quiescence_grace_s

    def generate_daily_report(self, report_date, retrospective_context, weekly_lessons="",
                              market_data="", screening_data=""):
        start = time.monotonic()
        try:
            raw = _run_sync(self._run_squad(report_date, retrospective_context,
                                            weekly_lessons, market_data, screening_data))
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("multica squad path errored, falling back: %s", exc)
            raw = None
        if raw and parse_report_content(raw) is not None:
            return raw, time.monotonic() - start
        logger.warning("multica squad produced no parseable report — using in-process fallback")
        return self._fallback.generate_daily_report(report_date, retrospective_context,
                                                     weekly_lessons, market_data, screening_data)

    def generate_weekly_report(self, report_date, weekly_stats, detailed_performance, closed_rationales=""):
        # Weekly stays in-process (design decision).
        return self._fallback.generate_weekly_report(report_date, weekly_stats,
                                                      detailed_performance, closed_rationales)

    async def _run_squad(self, report_date, retro, weekly_lessons, market_data, screening) -> str | None:
        if not await self._multica.health():
            return None
        issue = await self._multica.create_issue(
            title=f"[daily-report] {report_date.isoformat()} trading report",
            body=self._compose_brief(report_date, retro, weekly_lessons, market_data, screening),
            labels=["daily-report"], assignee_id=self._squad_id)
        if issue is None or not issue.id:
            return None
        await self._await_completion(issue.id)
        comments = await self._multica.list_comments(issue_id=issue.id)
        for c in reversed(comments):  # newest first; prefer agent (leader) synthesis
            env = extract_report_json(c.content)
            if env and parse_report_content(env) is not None:
                return env
        return None

    async def _await_completion(self, issue_id: str) -> None:
        deadline = time.monotonic() + self._timeout
        quiet_since: float | None = None
        while time.monotonic() < deadline:
            state = await self._multica.get_issue(issue_id=issue_id)
            if state and state.status in _TERMINAL:
                return
            runs = await self._multica.list_runs(issue_id=issue_id)
            active = any(r.status in ("running", "queued") for r in runs)
            done = [r for r in runs if r.status == "completed"]
            if not active and len(done) >= 2:  # ≥ leader + 1 member ran
                now = time.monotonic()
                quiet_since = quiet_since or now
                if now - quiet_since >= self._grace:
                    return
            else:
                quiet_since = None
            await asyncio.sleep(self._poll)

    @staticmethod
    def _compose_brief(report_date, retro, weekly_lessons, market_data, screening) -> str:
        return (
            f"# Daily KR+US Trading Report — {report_date.isoformat()}\n\n"
            "Run the Investment Council. The **Portfolio Manager (leader)** must, once members "
            "have contributed, post the FINAL report as a single fenced ```json block matching "
            "the house schema (report_date, market_summary, alert_banner, news_items, "
            "causal_chains, risk_matrix, sector_analysis, sentiment, technicals, recommendations "
            "[ticker,name,market,direction,timeframe,entry,target,stop,rationale], upcoming_events, "
            "disclaimer) and set this issue's status to in_review. Everything except live orders.\n\n"
            f"## Retrospective\n{retro or '-'}\n\n## Weekly lessons\n{weekly_lessons or '-'}\n\n"
            f"## Market data\n{market_data or '-'}\n\n## Screening\n{screening or '-'}\n"
        )
```

- [ ] **Step 4: Run** `cd backend && uv run pytest tests/test_multica_squad_report_provider.py -q` → Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat(council): MulticaSquadReportProvider happy path"`

### Task B5: Provider fallback paths (timeout, no JSON, Multica down)

**Files:** same provider; add tests to `test_multica_squad_report_provider.py`.

- [ ] **Step 1: Write failing tests** for three cases, each asserting the fallback's sentinel is returned:
  - `health()` returns False → fallback used, `create_issue` never called.
  - completion times out (`get_issue` always `in_progress`, runs always `running`) with `timeout_s=0` → fallback.
  - comments contain no parseable JSON → fallback.

```python
class StubFallback:
    def generate_daily_report(self, *a, **k): return ("FALLBACK_RAW", 0.0)
    def generate_weekly_report(self, *a, **k): return ("FALLBACK_WEEKLY", 0.0)

def test_falls_back_when_multica_unhealthy():
    class Down(FakeMultica):
        async def health(self): return False
        async def create_issue(self, **k): raise AssertionError("must not create")
    p = MulticaSquadReportProvider(multica=Down(), squad_id="sq1", fallback=StubFallback(),
                                   poll_interval_s=0, timeout_s=0, quiescence_grace_s=0)
    raw, _ = p.generate_daily_report(date(2026,6,2), "retro")
    assert raw == "FALLBACK_RAW"
```

- [ ] **Step 2: Run** → Expected: the unhealthy/no-JSON tests already pass with B4 logic; the
timeout test passes because `_await_completion` exits on deadline and extraction yields None.
Adjust the implementation only if a test fails.
- [ ] **Step 3: Commit** `git commit -am "test(council): squad provider fallback paths"`

### Task B6: Wire the provider in dependencies + config/constants

**Files:** Modify `infrastructure/dependencies.py`, `config.py`, `constants.py`.

- [ ] **Step 1:** Add `multica_squad_id: str = ""` to `config.py` Settings.
- [ ] **Step 2:** Add to `constants.py`:

```python
MULTICA_SQUAD_NAME = "Investment Council"
MULTICA_POLL_INTERVAL_S = 15
MULTICA_REPORT_TIMEOUT_S = 1500  # 25 min
MULTICA_QUIESCENCE_GRACE_S = 60
```

- [ ] **Step 3:** In `dependencies.py` `get_report_provider`, build the in-process
`CouncilReportProvider` as today, then if `settings.multica_base_url` and a squad id is
resolvable (use `settings.multica_squad_id` or resolve `MULTICA_SQUAD_NAME` via a one-shot
`GET /api/squads` using the existing `MulticaHTTPClient`), return:

```python
return MulticaSquadReportProvider(
    multica=multica, squad_id=squad_id, fallback=council,
    poll_interval_s=MULTICA_POLL_INTERVAL_S,
    timeout_s=MULTICA_REPORT_TIMEOUT_S,
    quiescence_grace_s=MULTICA_QUIESCENCE_GRACE_S,
)
```

Otherwise log a one-line warning ("squad unresolved → in-process council") and return `council`.

- [ ] **Step 4: Write a wiring test** in `backend/tests/test_dependencies.py`: with no
`MULTICA_BASE_URL`, `get_report_provider(...)` returns a `CouncilReportProvider`; with a
base url + squad id, returns `MulticaSquadReportProvider`.
- [ ] **Step 5: Run** `cd backend && uv run pytest tests/test_dependencies.py -q` → Expected: PASS.
- [ ] **Step 6: Commit** `git commit -am "feat(di): wire MulticaSquadReportProvider with in-process fallback"`

### Task B7: Upgrade the squad skill + member instructions in register-agents

**Files:** Modify `scripts/multica-register-agents.py`.

- [ ] **Step 1:** Change the `SKILL["content"]` to a strict spec: the leader's FINAL
deliverable is one fenced ```json block matching the schema in B4's `_compose_brief`
(list every field), and the leader sets status `in_review` when done.
- [ ] **Step 2:** Append to each non-leader agent's `instructions`: "When you finish your
part, post your result as a comment and @mention the Portfolio Manager (the squad leader) so
they can synthesize the final report."
- [ ] **Step 3:** Re-run registration to update the live workspace (idempotent script does
not update existing agents — add an `--update` path OR document re-create). Minimal: add
`PATCH /api/agents/{id}` + `PUT /api/skills/{id}` calls when fields differ.
- [ ] **Step 4: Verify** `python3 scripts/multica-register-agents.py` runs clean and
`multica skill get "Daily Trading Report"` shows the strict spec.
- [ ] **Step 5: Commit** `git commit -am "feat(multica): strict report-JSON skill + member→leader handoff"`

### Task B8: Live integration test + end-to-end validation

**Files:** Create `backend/tests/test_multica_squad_integration.py` (guarded by `--integration`).

- [ ] **Step 1:** Write an integration test that (only when `--integration`) builds a real
`MulticaHTTPClient` from `.env`, creates a small squad-assigned issue ("one-line KOSPI bias,
output as ```json {\"market_summary\":...}```"), polls with a short timeout, and asserts
either a parseable envelope OR a clean fallback (never raises).
- [ ] **Step 2: Run** `cd backend && uv run pytest tests/test_multica_squad_integration.py --integration -q` → Expected: PASS (stack must be up).
- [ ] **Step 3: Full live run:** `cd backend && uv run daily-scheduler run --verbose` with the
stack up; confirm in the log it created a `[daily-report]` issue assigned to the squad, polled,
extracted a report (or fell back), and emailed. Verify the issue in Multica is **assigned**
(not unassigned) and the agents produced comments.
- [ ] **Step 4: Run** `make test` → Expected: all green (pylint 10.00 included).
- [ ] **Step 5: Commit** `git commit -am "test(multica): live squad integration + e2e daily run"`

---

## Final verification
- [ ] `make test` green.
- [ ] `make multica-status` healthy; a real `daily-scheduler run` creates a squad-**assigned**
  issue, the council executes inside Multica, and an email is produced.
- [ ] No `run-news` / `run-global-news` anywhere (`grep -rn "run-news\|global-news" . --include=*.py --include=Makefile --include=*.sh`).
- [ ] Update memory: supersede the "in-process council is settled" note with "daily report
  runs via Multica squad; in-process is fallback only."
