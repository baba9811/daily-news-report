# Design: Multica-Squad Council + Report-Only System

- **Date:** 2026-06-02
- **Status:** Draft for review
- **Author:** Claude (with user direction)

## 1. Problem & Motivation

The system today claims to "use Multica" but does not. Verified live on 2026-06-02:

- The investment council runs **entirely in-process**: `daily-scheduler` shells out
  to `claude -p` (opus) and `codex exec` (gpt-5.5) directly via
  `debate_engine.py` + the `claude_code_provider` / `codex_provider` adapters.
  A real `run-news` invocation made 14 direct subprocess LLM calls.
- Multica is used only for (a) **cosmetic registration** of agents/squad/skill and
  (b) **outbound failure issues** when a debate does not converge.
- Consequently **every Multica issue is `unassigned`** — the registered Multica
  agents never do the actual work; our backend does.

The user wants two changes:

1. **Run the council THROUGH Multica.** Assign the work to the registered
   "Investment Council" squad and let Multica's runtime orchestrate the agents,
   so issues are genuinely assigned and the agents genuinely execute.
2. **Strip the system to the report only.** Remove the two news-only briefing
   pipelines (Korean news, global/English news); keep the daily trading report,
   the weekly retrospective, and the bilingual (KO↔EN) report feature.

## 2. Verified Facts (live, against the running self-host stack + cloned source)

- `multica issue create --assignee-id <squad>` assigns an issue to a squad
  (`assignee_type=squad`). Creating it **immediately enqueues a task for the
  squad leader** (confirmed by `squad_assign_trigger_test.go` and live DAI-8).
- Squad execution is genuine LLM orchestration: the **leader (Portfolio Manager)**
  runs first (`kind=direct`), reads the issue, and **delegates by `@mention`**
  in a comment, which dispatches a `kind=comment` run for the mentioned member.
  Members post their work as comments. (Live: PM → `@News Sentiment Analyst`.)
- The leader follows a hard-coded **"Squad Operating Protocol"**
  (`server/internal/handler/squad_briefing.go`): coordinate, delegate, record an
  evaluation (`multica squad activity`), **stop after dispatch**, and be
  **re-triggered** when "a delegated member posts an update", "a member finishes
  and the issue moves forward", or "someone @mentions you again".
- **Reliability risk (observed):** in DAI-8 the member posted a plain answer that
  did *not* @mention the leader, the issue status did not advance, the leader was
  **not** re-triggered, and the issue stalled at `in_progress` with no final
  synthesis. The design MUST make completion + final synthesis deterministic from
  our side rather than trusting autonomous leader closure.
- Outbound issue API contract verified correct against source
  (`POST /api/issues {title,description,priority,status}`, `Bearer` + `X-Workspace-ID`).
- Report JSON contract (consumed by `parse_report_content` / rendered by Jinja2):
  `report_date, market_summary, alert_banner, news_items, causal_chains,
  risk_matrix, sector_analysis, sentiment, technicals, recommendations,
  upcoming_events, past_performance_commentary, disclaimer`.

## 3. Goals / Non-Goals

**Goals**
- Daily trading report is produced by the Investment Council **squad inside Multica**.
- Deterministic completion detection + final-report extraction from our side.
- In-process council retained as a **fallback only** (Multica down / squad timeout /
  unparseable output) so the daily email never silently fails.
- Remove the two news-only briefing pipelines end-to-end.
- Keep: daily report, weekly retrospective, bilingual (KO↔EN) report, dashboard.

**Non-Goals**
- No live order execution (unchanged).
- Weekly retrospective stays on the in-process council for now (it is report-producing
  and out of the squad-migration scope); may move to a squad later.
- No change to the inbound autopilot webhook in this work (tracked separately).

## 4. Scope of Removal (Part A)

Remove the Korean news (`run-news`) and global/English news (`run-global-news`)
briefing pipelines entirely:

- **CLI** (`entrypoints/cli/commands.py`): delete `run_news`, `run_global_news`.
- **Use case**: delete `RunNewsBriefingPipeline` (`run_news_pipeline.py`) — used only
  by the two news pipelines. Keep `RunDailyPipeline`, `RunWeeklyPipeline`.
- **Provider**: drop `generate_news_briefing` / `generate_global_news_briefing` from
  `NewsProviderPort` and `CouncilNewsProvider`. Keep `generate_daily_report`,
  `generate_weekly_report`. (Rename `CouncilNewsProvider` → `CouncilReportProvider`.)
- **Dependencies**: delete `get_news_pipeline`, `get_global_news_pipeline`.
- **Schedulers**: delete `scheduler/install-news*.sh`, `install-global-news*.sh`,
  `run_news.sh`, `run_global_news.sh`; remove their Makefile targets (`news-scheduler-*`,
  `global-news-scheduler-*`) and the `make dev` trap lines that boot them; remove the
  `com.dailyscheduler.news` / `.global-news` launchd plists.
- **Frontend**: remove news tab(s)/page(s) and routes that surface only news briefings.
- **Tests**: remove news-pipeline-specific tests; keep council/daily/weekly tests.
- **Docs**: update `README.md`, `SPEC.md`, `constants.py` comments (`NEWS_SCHEDULE_TIME`).

Keep the bilingual feature: `deliver_translation.py`, `translator`,
`REPORT_LANGUAGE` / `REPORT_SECONDARY_LANGUAGE`, dual email.

## 5. Architecture (Part B)

### 5.1 Components & boundaries (hexagonal)

- **Domain port `MulticaPort`** — extended with the operations the squad flow needs,
  all best-effort:
  - `create_issue(*, title, body, labels, assignee_id=None) -> MulticaIssue | None`
  - `get_issue(issue_id) -> MulticaIssueState | None` (status)
  - `list_comments(issue_id) -> list[MulticaComment]`
  - `list_runs(issue_id) -> list[MulticaRun]` (status: running/queued/completed/failed)
  - existing `add_comment`, `health`
- **Adapter `MulticaHTTPClient`** — implements the new methods against the real API
  (`POST /api/issues` with `assignee_type=squad`+`assignee_id`; `GET /api/issues/{id}`,
  `/comments`, `/runs`). Reuses verified auth/headers.
- **Adapter `MulticaSquadReportProvider`** (new, in `adapters/council/`) — implements
  `generate_daily_report(...) -> (report_json_str, elapsed_s)`. Holds:
  - a `MulticaPort` (squad ops),
  - the resolved squad id (from `MULTICA_SQUAD_NAME`/`MULTICA_SQUAD_ID`),
  - a **fallback** `CouncilReportProvider` (in-process council).
- **Wiring** (`dependencies.py`): `get_news_provider` (→ rename `get_report_provider`)
  returns `MulticaSquadReportProvider(multica=…, fallback=CouncilReportProvider(…))`
  when `MULTICA_BASE_URL` + write creds + a resolvable squad are present; otherwise the
  in-process `CouncilReportProvider` directly. `weekly` keeps using
  `CouncilReportProvider.generate_weekly_report`.

### 5.2 Sequence (daily report)

```
launchd (SCHEDULE_TIME) → daily-scheduler run → RunDailyPipeline
  → provider.generate_daily_report(date, retro, weekly_lessons, market_data, screening)
      MulticaSquadReportProvider:
        1. compose issue description = inputs + STRICT instruction to output the
           final report as a single fenced ```json block matching the schema,
           and to set status → in_review when done.
        2. create_issue(assignee_id=<Investment Council squad>, labels=["daily-report"])
        3. poll loop (interval=MULTICA_POLL_INTERVAL_S, timeout=MULTICA_REPORT_TIMEOUT_S):
             done when issue.status ∈ {in_review, done}
             OR quiescent: no run running/queued for MULTICA_QUIESCENCE_GRACE_S
                AND ≥1 leader run + ≥1 member run completed
        4. extract: scan comments newest→oldest for a parseable ```json report
           envelope (prefer the leader's). Validate via parse_report_content.
        5. success → return (report_json, elapsed)
           failure (timeout / no parseable report / Multica error):
             - best-effort create_issue(labels=["infra"]) noting the failure
             - FALLBACK → self._fallback.generate_daily_report(...) (in-process council)
  → RunDailyPipeline renders HTML, saves, emails, then bilingual translation+dual email
```

### 5.3 Squad orchestration contract

To make autonomous closure reliable (mitigating the re-trigger risk), we control the
prompt surface we own:

- **Skill "Daily Trading Report"** (registered via `multica-register-agents.py`):
  upgrade from prose to a **strict spec** — the leader's FINAL deliverable is one
  fenced ```json block matching the exact schema; everything except live orders.
- **Issue description** (generated per run): embed today's inputs and an explicit
  acceptance contract: "When members have contributed, the **leader** posts the final
  report as a single ```json block and sets the issue status to `in_review`."
- **Member instructions** (agent specs): add "when you finish your part, @mention the
  Portfolio Manager (leader) so they can synthesize," to encourage re-trigger.
- Our **quiescence backstop** guarantees we still extract a result even if the leader
  never advances status — so correctness does not *depend* on the LLM closing the loop.

### 5.4 Configuration (constants.py / .env)

- `.env`: `MULTICA_SQUAD_ID` (optional explicit id) — secret-free, may live in `.env`
  since it is environment-specific like the workspace id.
- `constants.py`: `MULTICA_SQUAD_NAME = "Investment Council"`,
  `MULTICA_POLL_INTERVAL_S`, `MULTICA_REPORT_TIMEOUT_S` (~25 min),
  `MULTICA_QUIESCENCE_GRACE_S` (~60 s). Add `MULTICA_BACKOFF_BASE_S` (retry backoff —
  audit nit).

### 5.5 make / setup

- `make dev` continues to bring up the stack (`multica.sh up-soft`). Document that
  `make multica-agents-setup` (runtime daemon + register agents/squad/skill) is a
  required **one-time** step; add a fast pre-flight in the provider that, if the squad
  cannot be resolved, logs a clear instruction and uses the in-process fallback.

## 6. Testing (SDD + TDD)

- **Schema first**: dataclasses for `MulticaIssueState`, `MulticaComment`, `MulticaRun`;
  the report JSON schema is already pinned by `parse_report_content`.
- **Unit (mocked port)**: `MulticaSquadReportProvider` against a fake `MulticaPort` that
  scripts: create → runs(running) → comments(leader json) → status(in_review). Assert
  extraction, quiescence path, timeout→fallback, unparseable→fallback.
- **Adapter unit**: `MulticaHTTPClient` new methods against `httpx.MockTransport`.
- **Integration (`--integration`)**: live stack — create a squad-assigned issue with a
  tiny report task, poll, extract; assert a parseable envelope or graceful fallback.
- Keep `make test` green (pytest, pyrefly, pylint 10.00, mypy, frontend typecheck/oxlint).

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Leader doesn't auto-close (observed) | Quiescence backstop extraction; skill/issue contract; member→leader @mention |
| Squad latency (real LLM debate) | 25-min timeout, then in-process fallback; runs in background per schedule |
| Leader emits prose, not JSON | Strict skill spec + fenced-block requirement; `parse_report_content` validation; fallback on parse failure |
| Multica/daemon down | `health()` pre-check → in-process fallback; daily email preserved |
| Squad not registered on fresh clone | Pre-flight resolve + clear log + fallback; document `make multica-agents-setup` |

## 8. Rollout

1. Part A (remove news) — isolated, keeps `make test` green.
2. Extend `MulticaPort` + `MulticaHTTPClient` (schema + adapter + unit tests).
3. `MulticaSquadReportProvider` + wiring + fallback (unit tests).
4. Skill/agent contract upgrade in `multica-register-agents.py`.
5. Integration test + a live end-to-end daily run validated against the stack.
6. Update README/SPEC; update memory (supersede the "in-process is settled" note).

## 9. Open Questions

- Weekly retrospective: keep in-process now (assumed). Move to squad later? (Deferred.)
- Should `make dev` auto-run `multica-agents-setup` when the squad is missing, or only
  warn? (Leaning: warn + fallback, to avoid surprising daemon installs in `make dev`.)
