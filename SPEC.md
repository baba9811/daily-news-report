# SPEC.md - Intent Specification

> This document describes **WHAT** the system does — verifiable behaviors and acceptance criteria.
> For **HOW** to build it (architecture, conventions, tooling), see [CLAUDE.md](CLAUDE.md).
> Each spec item has a unique ID (`SECTION-NN`) that can be referenced from test names.

## System Purpose

AI-powered daily trading report system for Korean (KOSPI/KOSDAQ) and US (NYSE/NASDAQ) markets.
Runs autonomously via scheduler, generates news-driven analysis and recommendations using Claude AI,
tracks recommendation outcomes over time, and feeds performance data back into future reports
as a self-improving retrospective loop. Delivers reports via email and provides a web dashboard.

## Spec ID Convention

- Format: `SECTION-NN` (e.g., `PIPE-01`, `REC-03`)
- Tests should reference spec IDs in names where practical: `test_pipe_01_idempotent_skip`
- Multiple tests can cover one spec ID (different scenarios)

---

## Daily Pipeline (PIPE-*)

- [ ] `PIPE-01`: If a daily report already exists for today, the pipeline skips and returns success (idempotency)
- [ ] `PIPE-02`: Pipeline executes 9 sequential steps: check recommendations → update prices → build retrospective → fetch market data → screen stocks → generate report (Claude CLI) → parse response → save to DB + filesystem → send email
- [ ] `PIPE-03`: Report generation sends Claude CLI: retrospective context, weekly lessons (Mondays only), real-time market data, stock screening data
- [ ] `PIPE-04`: Response parsing tries JSON first; falls back to legacy HTML extraction if JSON parse fails
- [ ] `PIPE-05`: Empty Claude response causes pipeline failure and triggers error email
- [ ] `PIPE-06`: Unexpected exceptions are caught, logged, error email sent, pipeline returns false
- [ ] `PIPE-07`: Email failure does NOT cause pipeline failure — report is still saved
- [ ] `PIPE-08`: Reports are saved to both DB (SQLite) and filesystem (`data/reports/YYYY-MM-DD_daily.html`)
- [ ] `PIPE-09`: Monday reports include weekly analysis lessons in the prompt context
- [ ] `PIPE-10`: Stock screening covers defined universe (~63 KR + ~38 US stocks) with fundamental and technical data

## Recommendation Lifecycle (REC-*)

- [ ] `REC-01`: New recommendations start with status `OPEN`
- [ ] `REC-02`: DAY trades expire after `DAY_TRADE_EXPIRY_DAYS` (default 1 day); same-day trades are NOT expired
- [ ] `REC-03`: SWING trades expire after `SWING_TRADE_EXPIRY_DAYS` (default 14 days)
- [ ] `REC-04`: LONG target hit when `current_price >= target_price` → status `TARGET_HIT`
- [ ] `REC-05`: LONG stop hit when `current_price <= stop_loss` → status `STOP_HIT`
- [ ] `REC-06`: SHORT target hit when `current_price <= target_price` → status `TARGET_HIT`
- [ ] `REC-07`: SHORT stop hit when `current_price >= stop_loss` → status `STOP_HIT`
- [ ] `REC-08`: On target/stop hit: status changes, `closed_at` set, `closed_price` recorded, `pnl_percent` calculated
- [ ] `REC-09`: PnL LONG = `(closed_price - entry_price) / entry_price * 100`; PnL SHORT = `(entry_price - closed_price) / entry_price * 100`
- [ ] `REC-10`: If price fetch fails (returns None), recommendation is left unchanged
- [ ] `REC-11`: Expiry check runs BEFORE price check — expired trades skip price checking
- [ ] `REC-12`: Each recommendation has: ticker, name, market, direction (LONG/SHORT), timeframe (DAY/SWING), entry/target/stop prices, rationale, sector

## Report Content (RPT-*)

- [ ] `RPT-01`: Report contains: market_summary, alert_banner, news_items, causal_chains, risk_matrix, sector_analysis, sentiment, technicals, recommendations, upcoming_events, past_performance_commentary, disclaimer
- [ ] `RPT-02`: News items have: category, headline, source, published_at, summary, impact_level, affected_sectors
- [ ] `RPT-03`: Recommendations include: risk_reward_ratio (>= 1.5), confidence level, causal_chain_summary
- [ ] `RPT-04`: HTML reports are rendered from Jinja2 template when JSON parsing succeeds
- [ ] `RPT-05`: Report language is controlled by `REPORT_LANGUAGE` env var (default: Korean)

## Retrospective (RETRO-*)

- [ ] `RETRO-01`: Daily retrospective looks back `RETROSPECTIVE_LOOKBACK_DAYS` (default 30 days)
- [ ] `RETRO-02`: Context includes: summary statistics, sector performance, strategy performance (DAY vs SWING), recent 7-day table, auto-derived lessons
- [ ] `RETRO-03`: Auto-derived lessons flag sectors with win rate below 30% as warnings, above 70% as opportunities
- [ ] `RETRO-04`: Auto-derived lessons compare DAY vs SWING win rates if difference exceeds 10 percentage points
- [ ] `RETRO-05`: Weekly analysis (Mondays only) computes: wins, losses, avg return, best/worst picks, sector breakdown
- [ ] `RETRO-06`: If no past data exists, context says "No past recommendation data available"

## API Contracts (API-*)

- [ ] `API-01`: `GET /api/dashboard` → latest report info, open rec count, 7-day win rate, 7-day closed count, today's alerts
- [ ] `API-02`: `GET /api/reports` → paginated list (`page`, `per_page`), filterable by `report_type`, sorted newest first
- [ ] `API-03`: `GET /api/reports/latest` → most recent daily report with HTML; 404 if none exist
- [ ] `API-04`: `GET /api/reports/{id}` → specific report; 404 if not found
- [ ] `API-05`: `GET /api/reports/{id}/html` → raw HTML with `text/html` content type
- [ ] `API-06`: `GET /api/performance/summary?period=30d` → total, open, target_hit, stop_hit, expired, win_rate, avg_pnl, best/worst picks
- [ ] `API-07`: `GET /api/performance/recommendations` → filterable by `status` (all/OPEN/TARGET_HIT/STOP_HIT/EXPIRED)
- [ ] `API-08`: `GET /api/performance/sectors?period=30d` → per-sector wins, losses, win_rate, avg_return
- [ ] `API-09`: `GET /api/performance/timeseries?period=30d` → daily data points with cumulative PnL and win rate
- [ ] `API-10`: `GET /api/retrospective/weekly` → paginated weekly analyses
- [ ] `API-11`: `GET /api/retrospective/daily-checks?limit=14` → recent daily check results
- [ ] `API-12`: `POST /api/pipeline/run` → triggers pipeline in background; returns `already_running` if in progress; prevents concurrent runs
- [ ] `API-13`: `GET /api/pipeline/status` → running state and last result
- [ ] `API-14`: `GET /api/settings` → current config with passwords masked as boolean
- [ ] `API-15`: `PUT /api/settings` → updates only safe fields (SMTP, email, claude_model, report_language); blocks claude_cli_path, database_url
- [ ] `API-16`: `POST /api/settings/test-email` → sends test email, returns success/failure
- [ ] `API-17`: `GET /api/settings/status` → health check: DB exists, Claude CLI reachable, SMTP configured

## Frontend Pages (UI-*)

- [ ] `UI-01`: Dashboard (`/`) shows: 4 stat cards (open recs, weekly closed, 7-day win rate, latest report date), win rate gauge, today's alerts list
- [ ] `UI-02`: Dashboard gracefully degrades — shows zeros/empty state when API is unavailable
- [ ] `UI-03`: Reports page (`/reports`) shows paginated list with date, type, summary (truncated 200 chars), generation time
- [ ] `UI-04`: Report detail (`/reports/[id]`) renders full HTML content of the report
- [ ] `UI-05`: Performance page (`/performance`) shows: PnL/win rate timeseries chart, sector breakdown bars, recommendations table
- [ ] `UI-06`: Retrospective page (`/retrospective`) shows: daily checks table, weekly analyses with sector breakdown
- [ ] `UI-07`: Settings page (`/settings`) shows: config form (safe fields only), system status indicators (DB, CLI, SMTP)

## Configuration Effects (CFG-*)

- [ ] `CFG-01`: `SCHEDULE_TIME` (env, HH:MM KST) controls daily pipeline run time
- [ ] `CFG-02`: `REPORT_LANGUAGE` (env) controls generated report language (ko/en/ja)
- [ ] `CFG-03`: `DAY_TRADE_EXPIRY_DAYS` (constants.py, default 1) controls DAY trade expiry window
- [ ] `CFG-04`: `SWING_TRADE_EXPIRY_DAYS` (constants.py, default 14) controls SWING trade expiry window
- [ ] `CFG-05`: `RETROSPECTIVE_LOOKBACK_DAYS` (constants.py, default 30) controls retrospective analysis range
- [ ] `CFG-06`: `RECENT_PERIOD_DAYS` (constants.py, default 7) controls "recent" window in retrospective table
- [ ] `CFG-07`: `CLAUDE_TIMEOUT_SECONDS` (constants.py, default 1200) controls max wait for Claude CLI
- [ ] `CFG-08`: `CLAUDE_RETRY_COUNT` / `CLAUDE_RETRY_DELAY_SECONDS` (constants.py) control Claude CLI retry behavior
- [ ] `CFG-09`: `EMAIL_MAX_RETRIES` / `EMAIL_BACKOFF_BASE` (constants.py) control email retry with exponential backoff
- [ ] `CFG-10`: `SUMMARY_MAX_LENGTH` (constants.py, default 200) controls report summary truncation

## Error Handling (ERR-*)

- [ ] `ERR-01`: Pipeline catches all exceptions, logs them, sends error email, returns false
- [ ] `ERR-02`: Email failure is non-fatal — reports are saved regardless
- [ ] `ERR-03`: Price fetch failure for one recommendation does not affect others
- [ ] `ERR-04`: Pipeline trigger endpoint prevents concurrent runs via thread lock
- [ ] `ERR-05`: Claude CLI calls have configurable timeout and retry with delay

## Data Integrity (DATA-*)

- [ ] `DATA-01`: Only one daily report per date (enforced by idempotency check)
- [ ] `DATA-02`: Reports persisted to both DB (queryable) and filesystem (portable HTML)
- [ ] `DATA-03`: Settings API blocks writes to security-sensitive fields (claude_cli_path, database_url)
- [ ] `DATA-04`: Secrets never exposed in API responses — password shown only as boolean `smtp_password_set`

---

## Agents (AGENT-*)

- [ ] `AGENT-01`: Each role has a canonical identifier, a default `BackendBinding`, and a default Jinja2 system prompt template
- [ ] `AGENT-02`: `agent_binding` SQLite table stores per-role overrides; absent row means use code default
- [ ] `AGENT-03`: UI `/agents/[role]` can update provider, model, and override system prompt; changes apply to subsequent debates only (running debates use the snapshot at start)
- [ ] `AGENT-04`: System prompts always include retrospective context block and auto-injected memory block (may be empty)
- [ ] `AGENT-05`: Analyst roles have `WebSearch` and `WebFetch` enabled; non-analyst roles have no tools by default
- [ ] `AGENT-06`: Per-pipeline team composition is static (defined in code); users cannot add/remove roles

## Debate (DEBATE-*)

- [ ] `DEBATE-01`: A daily debate executes Analyst (parallel) → Debate loop (Bull/Bear/Judge, up to `max_rounds=3`) → Trader → Risk Mgmt → PM
- [ ] `DEBATE-03`: Weekly pipeline runs sequentially without a debate loop (`max_rounds=0`)
- [ ] `DEBATE-04`: Each Speech is persisted with `tokens_in`, `tokens_out`, `latency_ms`, `cli_command_hash`
- [ ] `DEBATE-05`: LangGraph checkpoints are taken at each node boundary; checkpoints survive process restart
- [ ] `DEBATE-06`: When max_rounds is reached without convergence, `DebateGraph.state = MAX_ROUNDS_DISSENT`; pipeline still produces a Verdict (both sides' positions are forwarded to Trader/PM)
- [ ] `DEBATE-07`: `SubprocessPool` enforces a global `MAX_CONCURRENT_LLM_CALLS` constant (default 4)
- [ ] `DEBATE-08`: Only one debate per pipeline runs concurrently; manual trigger while one is running returns `already_running`
- [ ] `DEBATE-09`: Memory context is computed once at debate start and snapshotted into `DebateState`; mid-debate memory ingests do not affect the running debate
- [ ] `DEBATE-10`: The final `Verdict.report_content` schema is byte-compatible with the legacy `ReportContent` consumed by RPT-* downstream — existing parser and renderer continue to work unchanged

## Judge (JUDGE-*)

- [ ] `JUDGE-01`: Judge computes both rule_score and agreement_score for each round
- [ ] `JUDGE-02`: Convergence requires rule_score >= 0.75 AND agreement_score >= 0.70 AND not false_consensus
- [ ] `JUDGE-03`: false_consensus detection blocks convergence even if both scores pass
- [ ] `JUDGE-04`: Judge output includes `sharpening_questions[]` injected into next Bull and Bear prompts
- [ ] `JUDGE-05`: Judge uses a different provider than Bull/Bear by default (defaults: Bull/Bear=claude-code, Judge=codex)
- [ ] `JUDGE-06`: `ConsensusScore` is persisted per round and visible in `/debate/[id]`
- [ ] `JUDGE-07`: Three regression fixtures verify Judge behavior: clear-consensus (must converge), clear-dissent (must not converge), false-consensus (must detect and not converge)
- [ ] `JUDGE-08`: Thresholds (`rule_threshold=0.75`, `llm_threshold=0.70`) live in `constants.py`; not in `.env`

## Memory (MEM-*)

- [ ] `MEM-01`: Every completed debate produces one `MemoryNode` of kind `decision` per recommendation
- [ ] `MEM-02`: Weekly debate produces one `MemoryNode` of kind `lesson`
- [ ] `MEM-03`: Memory ingest is atomic: file write + DB row + tree update succeed or all roll back
- [ ] `MEM-04`: `query_metadata` filters by symbol, sector, strategy, outcome, date range; combined as AND
- [ ] `MEM-05`: `query_keyword` returns FTS5 BM25-ranked results using the trigram tokenizer (Korean partial match works)
- [ ] `MEM-06`: `traverse_tree` returns up to `max_depth` levels of node summaries to the LLM, then resolves selected leaves to file contents
- [ ] `MEM-07`: When a recommendation closes, the linked MemoryNode's `outcome` field and markdown frontmatter are updated
- [ ] `MEM-08`: Memory context block in agent system prompts is empty if no memory exists (no error)
- [ ] `MEM-09`: `data/memory/` is in `.gitignore` (private to deployment)
- [ ] `MEM-10`: Memory size cap: rebuild_tree truncates summaries when tree.json exceeds 200 KB (LLM context safety)

## UI Extended (UI-09+) and SSE (SSE-*)

- [ ] `UI-09`: `/agents` lists all roles for all pipelines with current provider badges
- [ ] `UI-10`: `/agents/[role]` allows changing provider/model/system_prompt; submit shows confirmation; change applies to next debate
- [ ] `UI-11`: `/debate` is paginated (page, per_page) and filterable
- [ ] `UI-12`: `/debate/[id]` shows analyst reports, all rounds with judge scores, trader/risk/pm cards
- [ ] `UI-13`: `/debate/[id]` live mode connects via SSE and renders events in order; reconnects on disconnect
- [ ] `UI-14`: `/memory` renders the tree from `tree.json` and shows file content on selection
- [ ] `UI-15`: `/memory` search uses FTS5 and highlights snippets in results
- [ ] `UI-16`: `/multica` iframes the Multica UI when the service is up; shows status indicator otherwise
- [ ] `UI-17`: `/dashboard` "Active debate" widget appears only when a debate is running
- [ ] `UI-18`: `/settings` reports CLI health (claude version, codex version) and Multica connectivity
- [ ] `SSE-01`: `GET /api/debate/{id}/stream` returns `text/event-stream` with cache-control: no-cache
- [ ] `SSE-02`: Stream events use named SSE events (`event: analyst_done` etc.) with JSON `data:` payloads
- [ ] `SSE-03`: Disconnected clients reconnect with `Last-Event-ID`; backend resumes from that index
- [ ] `SSE-04`: Replay of a finished debate emits all persisted events in order, then a final `debate_done` event, then closes

## Multica (MULTICA-*)

- [ ] `MULTICA-01`: `make dev` brings up the Multica self-host stack (multica-postgres, multica-backend, multica-frontend via `docker compose -f docker-compose.multica.yml`) alongside the native daily-scheduler backend + frontend + schedulers; `make multica-up/-stop/-down/-status/-logs` control the stack independently; Ctrl+C stops the stack (data volumes preserved)
- [ ] `MULTICA-02`: `MulticaHTTPClient.create_issue` succeeds when Multica is up; logs and continues when Multica is down (debate is not blocked)
- [ ] `MULTICA-03`: Debate failing to converge creates a Multica issue with label `dissent`
- [ ] `MULTICA-04`: Webhook signature is verified with HMAC-SHA256; mismatched signatures return 401
- [ ] `MULTICA-05`: `issue.assigned` with label `manual-trigger` and title matching `rerun {daily|weekly}` triggers the corresponding pipeline
- [ ] `MULTICA-06`: `/multica` UI iframes Multica frontend; falls back to status card when iframe load fails
- [ ] `MULTICA-07`: `/settings` shows Multica connectivity (up/down) with last-checked timestamp
- [ ] `MULTICA-08`: Multica integration is best-effort: outbound failures do not fail debates
- [ ] `MULTICA-09`: The daily report runs THROUGH the Multica "Investment Council" squad — `MulticaSquadReportProvider` creates a `[daily-report]` issue assigned (`assignee_type=squad`) to the squad, the runtime orchestrates the registered agents (leader delegates by @mention), and the provider polls `GET /api/issues/{id}/task-runs` + status to quiescence/terminal (`in_review`/`done`) before extracting the leader's final fenced-`json` report
- [ ] `MULTICA-10`: The squad path is robust — on Multica-unreachable, squad timeout, or unparseable output the provider falls back to the in-process `CouncilReportProvider` so the daily email is never lost; weekly retrospective always runs in-process

## Backend Providers (BACK-*)

- [ ] `BACK-01`: `ClaudeCodeProvider` invokes `claude -p` with prompt, model, output-format text, and configurable tools
- [ ] `BACK-02`: `CodexProvider` invokes `codex exec` with prompt, model, output-format json; parses the JSON envelope
- [ ] `BACK-03`: Neither provider requires an API key; both rely on the user's CLI subscription credentials
- [ ] `BACK-04`: `SubprocessPool` enforces `max_concurrent` across both providers
- [ ] `BACK-05`: Each subprocess call has a per-call `timeout_s` (default in `constants.py`); timeout triggers retry up to `RETRY_COUNT`
- [ ] `BACK-06`: Failed subprocess (exit != 0) after retries raises a domain exception captured by the pipeline; pipeline returns failure status, sends error email (existing behavior preserved)
- [ ] `BACK-07`: All subprocess calls log: command (with secrets redacted), prompt hash (first 16 hex chars of SHA-256), duration, exit code

## Configuration Extended (CFG-06+)

> Note: the council release re-uses the `CFG-*` prefix; `CFG-06`/`CFG-07` from the legacy retrospective section refer to lookback constants. The IDs below are the council-era extensions and are tracked separately by `constants.py` location.

- [ ] `CFG-06`: `MAX_CONCURRENT_LLM_CALLS` controls parallelism across all subprocess providers
- [ ] `CFG-07`: `JUDGE_RULE_THRESHOLD` and `JUDGE_LLM_THRESHOLD` are read from `constants.py`, not `.env`
- [ ] `CFG-08`: `MULTICA_BASE_URL` and `MULTICA_WEBHOOK_SECRET` are read from `.env`; missing values disable Multica integration gracefully
- [ ] `CFG-09`: `CODEX_CLI_PATH` defaults to `/usr/local/bin/codex` if unset; missing binary degrades JUDGE to fallback claude-code with warning logged

## Data Migration Extended (DATA-04+)

> Note: `DATA-04` already exists above (secrets never exposed). The IDs below are the council-era data migration extensions and refer to migration / multi-agent council tables.

- [ ] `DATA-04`: Migration runs idempotently on backend startup
- [ ] `DATA-05`: Existing recommendations remain accessible after migration; `debate_id` is NULL for legacy rows
- [ ] `DATA-06`: `memory/` directory and `memory_node` / `memory_fts` tables are created if missing
- [ ] `DATA-07`: FTS5 trigram tokenizer is available in the bundled SQLite (verified at startup; error logged with installation guidance if missing)

## Testing (TEST-*)

- [ ] `TEST-01`: All new components have unit test coverage; pylint score 10.00/10
- [ ] `TEST-02`: Three Judge regression fixtures (clear-converge, clear-dissent, false-consensus) exist and pass
- [ ] `TEST-03`: All existing SPEC items continue to pass (regression suite green)
- [ ] `TEST-04`: Playwright E2E covers the 6 new pages and 1 trigger flow
- [ ] `TEST-05`: Daily debate completes within 20 minutes on reference hardware

---

## Test Traceability

- Backend tests should include spec IDs in function names: `test_rec_02_day_trade_expires`
- Frontend E2E tests (Playwright) should follow same convention: `test_ui_01_dashboard_stat_cards`
- No mapping table maintained here — grep spec IDs across test files to find coverage
