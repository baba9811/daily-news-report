# Multi-Agent Investment Council — Design Spec

**Date**: 2026-05-25
**Status**: Design (pending implementation)
**Author**: Council brainstorming session
**References**: [TradingAgents (arxiv 2412.20138)](https://arxiv.org/abs/2412.20138), [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents), [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex), [llm-wiki-agent (Karpathy pattern)](https://github.com/SamurAIGPT/llm-wiki-agent), [Multica](https://github.com/multica-ai/multica), [SQLite FTS5](https://sqlite.org/fts5.html)

This document describes **WHAT** the multi-agent rewrite does and **HOW** the major components fit together. Implementation details (file paths, function signatures) belong in the subsequent implementation plan.

---

## 1. Overview

Rewrite `daily-scheduler` from a single-Claude-CLI report generator into a **multi-agent investment council** that produces reports through structured debate between specialized agents. Existing four pipelines (`daily`, `news`, `global-news`, `weekly`) are all migrated to the new debate engine in a single release. Existing acceptance criteria (`PIPE-*`, `REC-*`, `RPT-*`, `RETRO-*`, `API-*`, `UI-*`) must continue to pass — **no regressions**.

Council debate is implemented inside `daily-scheduler` using LangGraph. The companion [Multica](https://github.com/multica-ai/multica) board is integrated as the operations console for code/maintenance tasks executed by Claude Code and Codex agents on the same Docker network.

---

## 2. Goals & Non-Goals

### Goals
- Replace single-Claude-CLI report generation with multi-agent debate for all 4 pipelines (`daily`, `news`, `global-news`, `weekly`)
- Investment recommendations emerge from Bull/Bear debate convergence judged by a hybrid (rule + LLM) Judge
- All agent activity is visible in the UI — live progress (SSE) and post-hoc replay
- Agent backend per role is reconfigurable in the UI (Claude Code or Codex subprocess, model selection, system prompt preview)
- All LLM calls use subscription-based CLIs (`claude -p`, `codex exec`); no API keys required
- Reflection memory accumulates structured Markdown decisions, indexed by a JSON tree (PageIndex pattern) and SQLite FTS5 (BM25 + trigram), and is automatically injected into future debates
- Multica is co-deployed in `docker-compose` and bidirectionally integrated (event POST, webhook intake, UI iframe)
- All existing `SPEC.md` items continue to pass

### Non-Goals (deferred to future spec)
- Embedding-based semantic memory search (current spec is vectorless)
- Cross-language report localization beyond existing `REPORT_LANGUAGE` env var
- Live broker execution / paper trading integration
- Multi-tenant / multi-user authentication

---

## 3. Decisions Log

| # | Question | Decision | Key Constraint |
|---|---|---|---|
| Q1 | Multica's role | Code/ops console; debate lives in daily-scheduler | LangGraph in-process, Multica external |
| Q2 | Scope | Big-bang (all 4 pipelines) | Zero regressions on existing SPEC items |
| Q3 | Agent composition | Per-pipeline teams; roles fixed in code, backend bindings configurable via UI | Static team graphs, dynamic provider mapping |
| Q4 | Debate mechanic | Consensus-based with `max_rounds` cap (default 3) | Bull/Bear convergence judged each round |
| Q4b | Judge mechanism | Hybrid: rule (quantitative) AND LLM (qualitative); false-consensus detector | Two thresholds must both pass |
| Q5 | Agent backend | Subscription CLIs only — `claude -p`, `codex exec` | No API keys; subprocess pool with asyncio |
| Q6 | UI depth | Full visualization — live SSE + replay + manual trigger | New pages: `/agents`, `/debate`, `/memory`, `/multica` |
| Q7 | Memory model | Full reflection with auto-injection | Markdown + JSON tree + FTS5 (no embeddings) |
| Q8 | Multica integration | Full bidirectional | Docker-composed, HTTP client + webhook, UI iframe |

LangGraph chosen for debate orchestration: MIT license (Apache 2.0 compatible), TradingAgents reference implementation, native StateGraph checkpoint replay aligns with SSE streaming.

---

## 4. High-Level Architecture

The system extends the existing hexagonal (ports-and-adapters) backend.

```
┌────────────────────────────── FRONTEND (Next.js App Router) ───────────────────────────────┐
│ Existing: /dashboard /reports /performance /retrospective /settings                        │
│ New:      /agents /agents/[role] /debate /debate/[id] /memory /multica                     │
│ Streaming: EventSource → SSE endpoint                                                      │
└──────────────────────────────────────┬─────────────────────────────────────────────────────┘
                                       │ REST + SSE
┌──────────────────────────────────────┴─── BACKEND (FastAPI) ───────────────────────────────┐
│                                                                                             │
│  Application (Use Cases)                                                                    │
│    RunDailyDebate · RunNewsDebate · RunGlobalNewsDebate · RunWeeklyDebate                   │
│    StreamDebateProgress · ListDebates · GetDebate                                           │
│    QueryMemory · IngestMemory                                                               │
│    GetAgents · UpdateAgentBinding                                                           │
│    RouteToMulticaIssue · HandleMulticaWebhook                                               │
│    [existing] CheckRecs · UpdatePrices · BuildRetrospective · ScreenStocks · FetchMarket    │
│                                                                                             │
│  Domain                                                                                     │
│    DebateGraph · Round · Speech · Verdict · ConsensusScore                                  │
│    Agent · Role · BackendBinding · SystemPrompt                                             │
│    MemoryNode · IndexTree · MemoryQuery                                                     │
│    MulticaIssue · MulticaEvent                                                              │
│    [existing] Recommendation · Report · ReportContent · Retrospective                       │
│                                                                                             │
│  Ports (interfaces)                                                                         │
│    LLMProviderPort         — submit(prompt, tools?) → text                                  │
│    MemoryStorePort         — ingest / query_metadata / query_keyword / traverse_tree        │
│    DebateBusPort           — publish(debate_id, event) → subscribers                        │
│    MulticaPort             — create_issue / add_comment / list_agents / receive_webhook     │
│    [existing] NewsProviderPort · FinanceProviderPort · EmailSenderPort · ...                │
│                                                                                             │
│  Infrastructure (Adapters)                                                                  │
│    ClaudeCodeProvider       (claude -p subprocess via SubprocessPool)                       │
│    CodexProvider            (codex exec subprocess via SubprocessPool)                      │
│    SubprocessPool           (asyncio semaphore, timeout, retries)                           │
│    MarkdownMemoryStore      (file IO under data/memory/)                                    │
│    JSONTreeIndex            (tree.json, generated by ingest)                                │
│    SQLiteFTS5Search         (FTS5 virtual table, trigram tokenizer)                         │
│    MulticaHTTPClient        (httpx async, HMAC webhook verifier)                            │
│    SSEBroadcaster           (sse-starlette EventSource, in-memory pub/sub)                  │
│    [existing] ClaudeNewsProvider (legacy, kept for migration window only)                   │
│                                                                                             │
└─────────────┬───────────────────────────┬───────────────────────┬───────────────────────────┘
              │                           │                       │
              │ subprocess                │ HTTP                  │ file/db
              ▼                           ▼                       ▼
       ┌──────────────┐         ┌──────────────────┐    ┌─────────────────────┐
       │ claude / codex│         │ Multica (Docker) │    │ SQLite + FTS5 +     │
       │ CLI (사용자    │         │ Go + Postgres17  │    │ memory/*.md (FS)    │
       │ 구독 인증)     │         │ + Next.js 16     │    │                     │
       └──────────────┘         └──────────────────┘    └─────────────────────┘
```

---

## 5. Domain Model

### 5.1 New Entities

**`Agent`** — fixed role + dynamic binding:
- `role`: stable identifier (`KR_FUNDAMENTALS`, `US_FUNDAMENTALS`, `KR_TECHNICAL`, `US_TECHNICAL`, `NEWS_SENT`, `BULL`, `BEAR`, `TRADER`, `RISK_MGMT`, `PORTFOLIO_MGR`, `JUDGE`, `EDITOR`, `PUBLISHER`, `PERF_ANALYST`, `LESSONS_RESEARCHER`)
- `binding`: `BackendBinding { provider: "claude-code" | "codex", model: str, system_prompt_id: str, timeout_s: int }`
- `metadata`: display name (KR/EN), description, default tools (for CLI), pipeline membership

**`DebateGraph`** — one debate instance:
- `id`: ULID
- `pipeline`: `daily` | `news` | `global-news` | `weekly`
- `state`: `RUNNING` | `CONVERGED` | `MAX_ROUNDS` | `FAILED`
- `rounds`: `Round[]`
- `analyst_reports`: per-analyst structured JSON
- `verdict`: `Verdict | None`
- `started_at` / `ended_at`
- `triggered_by`: `scheduler` | `manual` | `multica`

**`Round`** — one Bull/Bear/Judge cycle:
- `index`: 0-based
- `bull_speech`, `bear_speech`: `Speech`
- `judge_score`: `ConsensusScore`
- `converged`: bool

**`Speech`** — one agent utterance:
- `agent_role`, `text`, `structured_json` (when applicable: top_picks, rationale, risk), `tokens_in`, `tokens_out`, `latency_ms`, `cli_command_hash`

**`ConsensusScore`** — Judge output:
- `rule_score`: 0~1 (direction · jaccard · risk · delta)
- `llm_score`: 0~1
- `false_consensus`: bool
- `next_round_questions`: `str[]`
- `dimensions`: `{direction, ticker_overlap, risk_band, delta_vs_prev}` with sub-scores

**`Verdict`** — final pipeline output (consumed by existing RPT/RETRO downstream):
- `report_content`: existing `ReportContent` shape (unchanged for compatibility)
- `recommendations`: existing `Recommendation` shape
- `debate_id`: reference back to debate
- `consensus`: `CONVERGED` | `MAX_ROUNDS_DISSENT`

**`MemoryNode`** — one decision/lesson/pattern entry:
- `id`: ULID
- `path`: file path under `data/memory/`
- `kind`: `decision` | `pattern` | `lesson`
- `symbol?`, `sector?`, `strategy?`, `outcome?`, `date`
- `summary`: <= 200 chars, used in tree.json
- `body`: full markdown content (file-backed, not stored in DB row)
- `linked_debate_id?`, `linked_recommendation_id?`

**`IndexTree`** — derived from `MemoryNode`s, persisted as `tree.json`:
- Hierarchical: by-date → by-sector → by-symbol → leaf, plus parallel branches `patterns/` and `lessons/`
- Each node: `{node_id, title, summary, child_ids[], file_paths[]}`

### 5.2 Ports (interfaces)

```python
class LLMProviderPort(Protocol):
    async def submit(self, prompt: str, tools: list[str] | None,
                     timeout_s: int, model: str) -> LLMResult: ...

class MemoryStorePort(Protocol):
    def ingest(self, node: MemoryNode) -> None: ...  # write file + update tree + FTS5 (single tx)
    def query_metadata(self, **filters) -> list[MemoryNode]: ...
    def query_keyword(self, text: str, limit: int = 10) -> list[MemoryNode]: ...  # BM25
    def traverse_tree(self, query: str, max_depth: int = 3) -> list[MemoryNode]: ...

class DebateBusPort(Protocol):
    def publish(self, debate_id: str, event: DebateEvent) -> None: ...
    async def subscribe(self, debate_id: str) -> AsyncIterator[DebateEvent]: ...

class MulticaPort(Protocol):
    async def create_issue(self, title: str, body: str, labels: list[str]) -> MulticaIssue: ...
    async def add_comment(self, issue_id: str, body: str) -> None: ...
    async def list_agents(self) -> list[MulticaAgent]: ...
    def verify_webhook(self, body: bytes, signature: str) -> bool: ...
```

---

## 6. Agents Specification

### 6.1 Per-pipeline team composition

| Pipeline | Roles (in execution order) | Max rounds |
|---|---|---|
| `daily` | KR_FUNDAMENTALS · US_FUNDAMENTALS · KR_TECHNICAL · US_TECHNICAL · NEWS_SENT (parallel analyst pool) → BULL ⇄ BEAR (+ JUDGE) → TRADER → RISK_MGMT → PORTFOLIO_MGR | 3 |
| `news` (KR) | NEWS_SENT(KR) · KR_TECHNICAL (parallel) → EDITOR ⇄ PUBLISHER (+ JUDGE) | 2 |
| `global-news` (US) | NEWS_SENT(US) · US_TECHNICAL (parallel) → EDITOR ⇄ PUBLISHER (+ JUDGE) | 2 |
| `weekly` | PERF_ANALYST → LESSONS_RESEARCHER → PORTFOLIO_MGR (no debate; sequential synthesis) | 1 (effectively 0 debate) |

### 6.2 Default backend bindings (configurable via UI)

| Role | Default provider | Default model | Tools | Why |
|---|---|---|---|---|
| Analyst roles (Fund/Tech/News+Sent) | `claude-code` | `opus` | `WebSearch`, `WebFetch` | Need real-time market/news data — CLI built-in tools mandatory |
| BULL / BEAR / EDITOR / PUBLISHER | `claude-code` | `opus` | `WebSearch` (limited) | Need to verify analyst claims, look up counter-evidence |
| TRADER | `claude-code` | `sonnet` | (none, reasoning only) | Position sizing, no external data needed |
| RISK_MGMT | `claude-code` | `opus` | (none) | Strict policy enforcement; max model |
| PORTFOLIO_MGR | `claude-code` | `opus` | (none) | Final synthesis |
| JUDGE | `codex` | `gpt-5-codex` (or whatever the current default) | (none) | Different model than debaters → reduces single-vendor bias in convergence judgment |
| PERF_ANALYST / LESSONS_RESEARCHER | `claude-code` | `sonnet` | (none) | Aggregation tasks |

The Judge using a **different vendor by default** is intentional: it reduces self-vendor bias when judging Bull/Bear (both Claude). Users can override.

### 6.3 System prompts

System prompts are stored as Jinja2 templates under `backend/src/daily_scheduler/templates/prompts/agents/<role>.md` and rendered with: pipeline context, market data, analyst reports (for debaters), prior round speeches (for Bull/Bear rounds 2+), retrospective context, and **auto-injected memory** (top 5 from `traverse_tree` ∪ `query_metadata`).

Templates ship with sensible defaults in code. UI can override per role via `agent_binding` table (override is stored, not the full prompt — base template + override diff).

### 6.4 Acceptance Criteria (AGENT-*)

- [ ] `AGENT-01`: Each role has a canonical identifier, a default `BackendBinding`, and a default Jinja2 system prompt template
- [ ] `AGENT-02`: `agent_binding` SQLite table stores per-role overrides; absent row means use code default
- [ ] `AGENT-03`: UI `/agents/[role]` can update provider, model, and override system prompt; changes apply to subsequent debates only (running debates use the snapshot at start)
- [ ] `AGENT-04`: System prompts always include retrospective context block and auto-injected memory block (may be empty)
- [ ] `AGENT-05`: Analyst roles have `WebSearch` and `WebFetch` enabled; non-analyst roles have no tools by default
- [ ] `AGENT-06`: Per-pipeline team composition is static (defined in code); users cannot add/remove roles

---

## 7. Debate Flow

### 7.1 LangGraph state graph (daily pipeline)

```
START
  ├─→ AnalystPool (parallel: KR_F, US_F, KR_T, US_T, NEWS) ──→ analyst_reports[]
  │
  ├─→ DebateLoop
  │     │
  │     ├─→ BULL_NODE (speech, sees analyst_reports + prior_rounds)
  │     ├─→ BEAR_NODE (speech, sees BULL + analyst_reports + prior_rounds)
  │     ├─→ JUDGE_NODE (rule + LLM → ConsensusScore)
  │     ├─→ CHECK_CONVERGENCE
  │     │     ├─ converged? → exit loop, state = CONVERGED
  │     │     ├─ rounds_done >= max_rounds? → exit loop, state = MAX_ROUNDS
  │     │     └─ else → next round
  │
  ├─→ TRADER_NODE (sees analyst_reports + final round + consensus)
  ├─→ RISK_MGMT_NODE (sees TRADER proposal + analyst_reports)
  ├─→ PM_NODE (sees everything → final ReportContent JSON)
  │
END
```

### 7.2 State object

```python
@dataclass
class DebateState:
    debate_id: str
    pipeline: str
    market_data: dict          # from existing FetchMarketData
    screening: dict            # from existing ScreenStocks (daily only)
    retrospective: dict        # from existing BuildRetrospective
    memory_context: list[MemoryNode]  # auto-injected
    analyst_reports: list[dict]
    rounds: list[Round]
    current_round_idx: int
    converged: bool
    verdict: ReportContent | None
    error: str | None
```

LangGraph's checkpoint store: SQLite-backed (`debate_state.db`). Checkpoint at each node boundary → SSE can replay any debate, including in-progress ones.

### 7.3 Concurrency

- `SubprocessPool` enforces `max_concurrent` (default 4) across all `LLMProviderPort.submit` calls within a single debate
- Analyst phase: all 5 calls dispatched, semaphore caps to 4 → near-parallel
- Debate phase: strictly sequential (Bull → Bear → Judge depends on each)
- Trader/Risk/PM: sequential
- Inter-debate concurrency: max 1 daily debate at a time (existing `prevents concurrent runs` from `API-12`)

### 7.4 Acceptance Criteria (DEBATE-*)

- [ ] `DEBATE-01`: A daily debate executes Analyst (parallel) → Debate loop (Bull/Bear/Judge, up to `max_rounds=3`) → Trader → Risk Mgmt → PM
- [ ] `DEBATE-02`: News and global-news debates skip Trader/Risk_Mgmt; use Editor/Publisher only with `max_rounds=2`
- [ ] `DEBATE-03`: Weekly pipeline runs sequentially without a debate loop (`max_rounds=0`)
- [ ] `DEBATE-04`: Each Speech is persisted with `tokens_in`, `tokens_out`, `latency_ms`, `cli_command_hash`
- [ ] `DEBATE-05`: LangGraph checkpoints are taken at each node boundary; checkpoints survive process restart
- [ ] `DEBATE-06`: When max_rounds is reached without convergence, `DebateGraph.state = MAX_ROUNDS_DISSENT`; pipeline still produces a Verdict (both sides' positions are forwarded to Trader/PM)
- [ ] `DEBATE-07`: `SubprocessPool` enforces a global `MAX_CONCURRENT_LLM_CALLS` constant (default 4)
- [ ] `DEBATE-08`: Only one debate per pipeline runs concurrently; manual trigger while one is running returns `already_running`
- [ ] `DEBATE-09`: Memory context is computed once at debate start and snapshotted into `DebateState`; mid-debate memory ingests do not affect the running debate
- [ ] `DEBATE-10`: The final `Verdict.report_content` schema is byte-compatible with the legacy `ReportContent` consumed by RPT-* downstream — existing parser and renderer continue to work unchanged

---

## 8. Judge Specification

### 8.1 Rule score (deterministic)

```
rule_score =
    0.40 × direction_agreement       # 1.0 if same buy/hold/sell, else 0.0
  + 0.30 × ticker_jaccard            # |bull ∩ bear| / |bull ∪ bear| (top 5 each)
  + 0.20 × (1 - normalized_risk_diff)  # 1.0 if same risk band, 0.0 if max diff
  + 0.10 × stability_vs_prev          # 1.0 if both sides stable across rounds
```

Threshold: `rule_score ≥ 0.75` to pass.

Each agent's structured JSON output must include `{direction: BUY|HOLD|SELL, top_tickers: [str], risk_band: LOW|MID|HIGH}`. Parser enforces; missing fields → JUDGE-FAIL on that round (forces continuation).

### 8.2 LLM score (qualitative)

JUDGE (Codex by default) receives:
- Both speeches (current round)
- All prior rounds' speeches (short summary if > 2 rounds)
- Rule score breakdown

Returns JSON:
```json
{
  "agreement_score": 0.0-1.0,
  "dimensions": {
    "logical_coherence": 0.0-1.0,
    "evidence_quality": 0.0-1.0,
    "remaining_disagreement": "<text>",
    "sharpening_questions": ["...", "..."]
  },
  "false_consensus_detected": true|false,
  "false_consensus_reason": "<text or null>"
}
```

Threshold: `agreement_score ≥ 0.70` AND `false_consensus_detected == false`.

### 8.3 Convergence rule

```
converged = (rule_score >= 0.75) AND (agreement_score >= 0.70) AND (not false_consensus)
```

Both quantitative AND qualitative thresholds must pass. False consensus blocks convergence regardless of scores.

### 8.4 False-consensus heuristics

LLM-side heuristics (in JUDGE prompt):
- One side's speech length dropped >40% from prior round with no new evidence
- One side adopts the other's terminology without engaging the substance
- Both sides "agree to disagree" without resolving the original disagreement

Rule-side check: if `direction_agreement` flipped from 0 to 1 between round N-1 and N without intermediate evidence, mark suspect → require LLM to clear.

### 8.5 Acceptance Criteria (JUDGE-*)

- [ ] `JUDGE-01`: Judge computes both rule_score and agreement_score for each round
- [ ] `JUDGE-02`: Convergence requires rule_score >= 0.75 AND agreement_score >= 0.70 AND not false_consensus
- [ ] `JUDGE-03`: false_consensus detection blocks convergence even if both scores pass
- [ ] `JUDGE-04`: Judge output includes `sharpening_questions[]` injected into next Bull and Bear prompts
- [ ] `JUDGE-05`: Judge uses a different provider than Bull/Bear by default (defaults: Bull/Bear=claude-code, Judge=codex)
- [ ] `JUDGE-06`: `ConsensusScore` is persisted per round and visible in `/debate/[id]`
- [ ] `JUDGE-07`: Three regression fixtures verify Judge behavior: clear-consensus (must converge), clear-dissent (must not converge), false-consensus (must detect and not converge)
- [ ] `JUDGE-08`: Thresholds (`rule_threshold=0.75`, `llm_threshold=0.70`) live in `constants.py`; not in `.env`

---

## 9. Memory System

### 9.1 Storage layout (`backend/data/memory/`)

```
memory/
├── index.md                      # human-readable router (LLM-wiki)
├── tree.json                     # machine-readable PageIndex tree
├── by-date/2026/05/24-daily.md   # daily debate digest
├── by-sector/semiconductor/SAMSUNG/2026-05-24.md
├── by-strategy/{DAY,SWING}/index.md
├── patterns/                     # cross-cutting patterns derived from outcomes
│   ├── high-rsi-with-falling-revenue.md
│   └── sector-rotation-tech-to-finance.md
└── lessons/                      # mid-level lessons (also fed by existing RETRO)
    └── 2026-W19-weekly.md
```

Each `.md` has YAML frontmatter:

```yaml
---
id: 01HXYZ...
kind: decision
date: 2026-05-24
symbol: SAMSUNG
sector: semiconductor
strategy: DAY
direction: BUY
outcome: pending  # later: TARGET_HIT | STOP_HIT | EXPIRED
debate_id: 01HABC...
recommendation_ids: [01H...]
---
```

### 9.2 SQLite schema (additive to existing DB)

```sql
CREATE TABLE memory_node (
  id           TEXT PRIMARY KEY,    -- ULID
  file_path    TEXT NOT NULL UNIQUE,
  kind         TEXT NOT NULL,       -- decision | pattern | lesson
  symbol       TEXT,
  sector       TEXT,
  strategy     TEXT,                -- DAY | SWING | NULL
  outcome      TEXT,                -- pending | TARGET_HIT | STOP_HIT | EXPIRED | NULL
  date         TEXT NOT NULL,       -- ISO 8601
  summary      TEXT NOT NULL,       -- <= 200 chars
  debate_id    TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);

CREATE VIRTUAL TABLE memory_fts USING fts5(
  body,
  summary,
  symbol UNINDEXED,
  sector UNINDEXED,
  content='',
  tokenize='trigram'    -- handles Korean partial matching
);
```

### 9.3 Tree (tree.json) generation

Tree is **derivable** — regenerated by `MarkdownMemoryStore.rebuild_tree()`:
- Root → branches `by-date`, `by-sector`, `by-strategy`, `patterns`, `lessons`
- Each branch has subnodes computed from `memory_node` rows
- Leaf nodes carry `file_paths`, `summary`, `symbol`, `outcome`
- Internal nodes carry aggregated `summary` (concat of children summaries, trimmed)
- Stored as `data/memory/tree.json`
- Single transaction with file write + DB insert + tree rebuild on each `ingest`

LLM traversal: agent receives `tree.json` (or a pruned subtree if too large), reasons "where is most likely", returns `node_ids[]` of leaves to read. Backend resolves to `file_paths[]`, agent's next call includes those file contents.

### 9.4 Auto-injection at debate start

```python
def build_memory_context(pipeline, state) -> list[MemoryNode]:
    by_meta = store.query_metadata(
        symbol__in=state.screening.tickers[:10],
        date__gte=today - 90d,
    )[:5]
    by_tree = store.traverse_tree(
        query=f"{state.market_data.regime} {pipeline}",
        max_depth=3,
    )[:5]
    # de-dup, prefer recent + outcome-known
    return deduplicate(by_meta + by_tree)[:5]
```

### 9.5 Outcome linkage

When existing `CheckRecommendations` use case closes a recommendation (TARGET_HIT / STOP_HIT / EXPIRED), the linked `MemoryNode.outcome` is updated and the markdown frontmatter is rewritten. This enables future debates to see realized outcomes.

### 9.6 Acceptance Criteria (MEM-*)

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

---

## 10. UI Specification

### 10.1 New pages

**`/agents`** — grid of role cards
- Cards grouped by pipeline (daily / news / global-news / weekly)
- Each card: role label (KR/EN), current provider badge (claude-code / codex), current model, last-used timestamp, "configure" link
- Sticky header: "Memory context preview" (link to /memory), "Active debate" indicator

**`/agents/[role]`** — single agent detail/config
- Read: current binding, default binding (from code), system prompt preview (rendered with empty context), recent speeches list
- Write: provider dropdown, model dropdown (provider-dependent), system prompt override textarea, timeout slider
- "Reset to default" button → deletes the `agent_binding` row
- Save → applies to next debate only (not running ones)

**`/debate`** — debate history list
- Filterable by pipeline, date range, consensus state
- Each row: pipeline · date · `CONVERGED` | `MAX_ROUNDS_DISSENT` · rounds · top recommendation
- "Run now" buttons per pipeline (manual trigger)

**`/debate/[id]`** — debate detail
- Header: pipeline, started_at, state, total tokens, total duration
- Timeline panel (vertical scroll):
  - Analyst phase: 5 collapsed cards, expand to see structured JSON
  - Round 1..N: Bull speech card, Bear speech card, Judge card (4-dimension chart + sharpening questions)
  - Trader / Risk / PM cards
- Live mode: SSE connection, new events stream in; auto-scroll toggle
- Replay mode (post-hoc): same UI, populated from persisted DB
- Side panel: ConsensusScore evolution chart (rule_score & agreement_score per round)
- "Linked report" link → existing `/reports/[id]`

**`/memory`** — knowledge base
- Left: tree (from `tree.json`), expand/collapse
- Center: Markdown preview of selected file
- Right: filters (symbol, sector, outcome, date range)
- Search box: FTS5 keyword search → ranked list with snippets

**`/multica`** — operations console
- Top: status pill (connected · degraded · offline), open issues count, active agents count
- Main: iframe to Multica's UI (cookie-shared origin via reverse proxy)
- Footer: recent webhook events log

### 10.2 Existing page extensions

- `/dashboard`: new widget "Active debate" (shows in-progress debate with pipeline + round number; clicks to `/debate/[id]`)
- `/reports/[id]`: header link to `/debate/[debate_id]` if available
- `/settings`: new section "Multi-agent" (CLI health: `claude --version`, `codex --version`, Multica connectivity, total tokens last 24h)

### 10.3 Streaming

- Backend: `GET /api/debate/{id}/stream` returns SSE (text/event-stream)
- Events: `analyst_start`, `analyst_done`, `round_start`, `speech_chunk`, `judge_done`, `round_end`, `phase_change`, `debate_done`, `error`
- Frontend uses native `EventSource` API; reconnect with last-event-id on disconnect
- Backend: in-memory pub/sub (`DebateBusPort` impl); LangGraph node callbacks publish events
- Replay (debate already finished): same endpoint replays persisted events in order, ending with `debate_done`

### 10.4 Acceptance Criteria (UI-* extended, SSE-*)

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

---

## 11. Multica Integration

### 11.1 Deployment

`docker-compose.yml` (new file at repo root) brings up four services on a shared network:

```yaml
services:
  multica-postgres:
    image: postgres:17
    # init script enables pgvector extension
  multica-backend:
    image: ghcr.io/multica-ai/multica-backend:latest
    depends_on: [multica-postgres]
    environment:
      MULTICA_WEBHOOK_URL: http://daily-scheduler-backend:8000/webhooks/multica
      MULTICA_WEBHOOK_SECRET: ${MULTICA_WEBHOOK_SECRET}
  multica-frontend:
    image: ghcr.io/multica-ai/multica-frontend:latest
    depends_on: [multica-backend]
  daily-scheduler-backend:
    build: ./backend
    environment:
      MULTICA_BASE_URL: http://multica-backend:8080
      MULTICA_WEBHOOK_SECRET: ${MULTICA_WEBHOOK_SECRET}
```

The local `claude` and `codex` CLI binaries are mounted into the Multica daemon's container (or run on host); user subscription is via OS-level OAuth credentials. Multica daemon auto-detects them on PATH.

### 11.2 Outbound events (daily-scheduler → Multica)

`MulticaHTTPClient` posts issues/comments on these triggers:
- **debate failed to converge** (`MAX_ROUNDS_DISSENT`) → create issue, label `dissent`, assignee `none`
- **regression detected** (any existing SPEC-* test fails in nightly job) → create issue, label `regression`
- **CLI degradation** (claude or codex exit code != 0 across N consecutive calls) → create issue, label `infra`
- **debate completed** → add comment to the pipeline's tracking issue (one issue per pipeline, reused)

Each call is `best-effort`: retry once with 2 s delay, log on failure, never raise upstream.

### 11.3 Inbound webhook (Multica → daily-scheduler)

`POST /webhooks/multica` with HMAC-SHA256 signature in `X-Multica-Signature` header:
- `issue.assigned`: if labeled `manual-trigger`, schedules the corresponding debate (e.g. issue title `"rerun daily"`)
- `agent.registered`: refresh `MulticaPort.list_agents()` cache
- `comment.added`: ignored for now (logged only)

Signature verification rejects on mismatch; rejected requests return 401 and are logged with truncated body.

### 11.4 UI integration

`/multica` page iframes Multica frontend at `http://localhost:3001` (or whatever port the compose file exposes). Same-origin via reverse proxy in dev (`next.config.mjs` rewrites) and prod.

### 11.5 Acceptance Criteria (MULTICA-*)

- [ ] `MULTICA-01`: `docker-compose up` brings up multica-postgres, multica-backend, multica-frontend, daily-scheduler-backend, daily-scheduler-frontend
- [ ] `MULTICA-02`: `MulticaHTTPClient.create_issue` succeeds when Multica is up; logs and continues when Multica is down (debate is not blocked)
- [ ] `MULTICA-03`: Debate failing to converge creates a Multica issue with label `dissent`
- [ ] `MULTICA-04`: Webhook signature is verified with HMAC-SHA256; mismatched signatures return 401
- [ ] `MULTICA-05`: `issue.assigned` with label `manual-trigger` and title matching `rerun {daily|news|global-news|weekly}` triggers the corresponding pipeline
- [ ] `MULTICA-06`: `/multica` UI iframes Multica frontend; falls back to status card when iframe load fails
- [ ] `MULTICA-07`: `/settings` shows Multica connectivity (up/down) with last-checked timestamp
- [ ] `MULTICA-08`: Multica integration is best-effort: outbound failures do not fail debates

---

## 12. Subprocess Pool & Subscription CLI

### 12.1 Pool design

```python
class SubprocessPool:
    def __init__(self, max_concurrent: int):
        self._sem = asyncio.Semaphore(max_concurrent)

    async def run(self, cmd: list[str], stdin: str, timeout_s: int,
                  retries: int) -> SubprocessResult:
        async with self._sem:
            for attempt in range(retries + 1):
                try:
                    return await self._spawn_and_wait(cmd, stdin, timeout_s)
                except (TimeoutError, NonZeroExit) as e:
                    if attempt == retries:
                        raise
                    await asyncio.sleep(self._backoff(attempt))
```

### 12.2 Claude Code adapter (`claude -p`)

```python
class ClaudeCodeProvider(LLMProviderPort):
    async def submit(self, prompt, tools, timeout_s, model):
        cmd = [self.cli_path, "-p", prompt,
               "--model", model,
               "--output-format", "text",
               "--permission-mode", "bypassPermissions",
               "--disallowed-tools", "Write,Edit,Bash,ExitPlanMode,EnterPlanMode,TodoWrite"]
        if tools:
            cmd += ["--tools", ",".join(tools)]
        result = await self.pool.run(cmd, stdin="", timeout_s=timeout_s, retries=2)
        return LLMResult(text=result.stdout, ...)
```

### 12.3 Codex adapter (`codex exec`)

```python
class CodexProvider(LLMProviderPort):
    async def submit(self, prompt, tools, timeout_s, model):
        # Codex exec mode reads prompt from stdin
        cmd = [self.cli_path, "exec", "--model", model, "--output-format", "json"]
        result = await self.pool.run(cmd, stdin=prompt, timeout_s=timeout_s, retries=2)
        # codex returns JSON envelope; extract text
        return LLMResult(text=json.loads(result.stdout)["output"], ...)
```

Exact codex flags will be verified against the CLI's `--help` during implementation; the design only commits to "shell out, stdin or arg prompt, parse stdout."

### 12.4 Acceptance Criteria (BACK-*)

- [ ] `BACK-01`: `ClaudeCodeProvider` invokes `claude -p` with prompt, model, output-format text, and configurable tools
- [ ] `BACK-02`: `CodexProvider` invokes `codex exec` with prompt, model, output-format json; parses the JSON envelope
- [ ] `BACK-03`: Neither provider requires an API key; both rely on the user's CLI subscription credentials
- [ ] `BACK-04`: `SubprocessPool` enforces `max_concurrent` across both providers
- [ ] `BACK-05`: Each subprocess call has a per-call `timeout_s` (default in `constants.py`); timeout triggers retry up to `RETRY_COUNT`
- [ ] `BACK-06`: Failed subprocess (exit != 0) after retries raises a domain exception captured by the pipeline; pipeline returns failure status, sends error email (existing behavior preserved)
- [ ] `BACK-07`: All subprocess calls log: command (with secrets redacted), prompt hash (first 16 hex chars of SHA-256), duration, exit code

---

## 13. Configuration & Constants

### 13.1 New constants (`constants.py`)

```python
MAX_CONCURRENT_LLM_CALLS = 4
MAX_DEBATE_ROUNDS_DAILY = 3
MAX_DEBATE_ROUNDS_NEWS = 2
MAX_DEBATE_ROUNDS_WEEKLY = 0  # weekly is sequential

JUDGE_RULE_THRESHOLD = 0.75
JUDGE_LLM_THRESHOLD = 0.70

CLI_TIMEOUT_ANALYST_S = 900
CLI_TIMEOUT_DEBATE_S = 600
CLI_TIMEOUT_DECISION_S = 600
CLI_TIMEOUT_JUDGE_S = 300

MEMORY_TREE_MAX_BYTES = 200_000
MEMORY_AUTO_INJECT_TOP_K = 5

SSE_KEEPALIVE_INTERVAL_S = 15
MULTICA_HTTP_TIMEOUT_S = 10
MULTICA_RETRY_COUNT = 1
```

### 13.2 New env vars (`.env.example`)

```
MULTICA_BASE_URL=http://multica-backend:8080
MULTICA_WEBHOOK_SECRET=<generate via openssl rand -hex 32>

# Inherited / unchanged: CLAUDE_CLI_PATH, CLAUDE_MODEL (now used as default for binding)
CODEX_CLI_PATH=/usr/local/bin/codex
CODEX_DEFAULT_MODEL=gpt-5-codex
```

### 13.3 Acceptance Criteria (CFG-* extended)

- [ ] `CFG-06`: `MAX_CONCURRENT_LLM_CALLS` controls parallelism across all subprocess providers
- [ ] `CFG-07`: `JUDGE_RULE_THRESHOLD` and `JUDGE_LLM_THRESHOLD` are read from `constants.py`, not `.env`
- [ ] `CFG-08`: `MULTICA_BASE_URL` and `MULTICA_WEBHOOK_SECRET` are read from `.env`; missing values disable Multica integration gracefully
- [ ] `CFG-09`: `CODEX_CLI_PATH` defaults to `/usr/local/bin/codex` if unset; missing binary degrades JUDGE to fallback claude-code with warning logged

---

## 14. Data Migration

Existing `daily_scheduler.db` schema is preserved. Migration adds:
- `agent_binding` table
- `debate` table (id, pipeline, state, started_at, ended_at, triggered_by, verdict_id?)
- `round` table (id, debate_id, idx, rule_score, llm_score, false_consensus, converged)
- `speech` table (id, round_id|debate_id, agent_role, text_path, structured_json, tokens_in, tokens_out, latency_ms)
- `memory_node` table
- `memory_fts` FTS5 virtual table
- (existing) `recommendation` gets new nullable columns: `debate_id`, `memory_node_id`

Migration runs idempotently on first start (`alembic upgrade head` or equivalent SQLAlchemy `create_all`). Backfill: existing recommendations get `debate_id=NULL`, treated as "legacy" in UI (no debate link).

Existing report HTML files under `data/reports/` are kept as-is. New debate ingredient files under `data/memory/` are created on first ingest.

### Acceptance Criteria (DATA-* extended)

- [ ] `DATA-04`: Migration runs idempotently on backend startup
- [ ] `DATA-05`: Existing recommendations remain accessible after migration; `debate_id` is NULL for legacy rows
- [ ] `DATA-06`: `memory/` directory and `memory_node` / `memory_fts` tables are created if missing
- [ ] `DATA-07`: FTS5 trigram tokenizer is available in the bundled SQLite (verified at startup; error logged with installation guidance if missing)

---

## 15. Testing Strategy

### 15.1 Unit tests (pytest, in-memory SQLite)

- Each port has at least one fake implementation for use-case tests
- Judge rule calculation: 6 fixtures covering each dimension
- Judge LLM score: mocked LLMProvider returning canonical JSON shapes
- DebateGraph state transitions: 4 cases (convergence in round 1, convergence in round 2, max rounds dissent, error mid-debate)
- MemoryStore: ingest atomicity, query_metadata combinations, FTS5 BM25 ranking, tree traversal
- SubprocessPool: concurrency limit, timeout, retry/backoff
- MulticaHTTPClient: success, retry-then-success, retry-then-fail, webhook signature verify/reject

### 15.2 Integration tests (`pytest --integration`)

- `claude -p` real invocation (CLI installed + subscription active)
- `codex exec` real invocation (idem)
- Multica HTTP roundtrip against `docker compose up multica-backend multica-postgres`
- SQLite FTS5 trigram Korean recall (`삼성전자` partial match → recovers `삼성전자우`)

### 15.3 E2E (Playwright via MCP)

- `/agents` → click role → change provider claude-code → codex → save → verify in `/agents` and trigger next debate uses codex
- `/debate` → "Run now" daily → live SSE shows analyst progress → rounds appear → final report link works → click memory link → memory entry exists with correct frontmatter
- `/memory` → search "삼성전자" → result list shows; click → preview renders markdown
- `/multica` → iframe loads (with Multica up); status badge "offline" (with Multica stopped)

### 15.4 Regression — existing SPEC items

A nightly job runs the full existing pytest suite plus the new tests. Acceptance: all existing `PIPE-*`, `REC-*`, `RPT-*`, `RETRO-*`, `API-*`, `UI-*`, `CFG-*`, `ERR-*`, `DATA-*` tests pass unchanged.

Performance regression budget: daily debate end-to-end ≤ 20 minutes (vs ~10 minutes legacy); CI fails if budget exceeded.

### 15.5 Acceptance Criteria (TEST-*)

- [ ] `TEST-01`: All new components have unit test coverage; pylint score 10.00/10
- [ ] `TEST-02`: Three Judge regression fixtures (clear-converge, clear-dissent, false-consensus) exist and pass
- [ ] `TEST-03`: All existing SPEC items continue to pass (regression suite green)
- [ ] `TEST-04`: Playwright E2E covers the 6 new pages and 1 trigger flow
- [ ] `TEST-05`: Daily debate completes within 20 minutes on reference hardware

---

## 16. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Codex CLI flag drift breaking adapter | Med | High | Pin to current major version in compose; adapter has feature-detection at startup; fallback to claude-code if codex unhealthy |
| Subprocess pool saturating system | Low | High | `MAX_CONCURRENT_LLM_CALLS=4` default; observability in `/settings` |
| Multica HTTP API changes (no published contract) | Med | Med | Adapter layer is thin; outbound is best-effort; webhook contract documented in this spec is authoritative for our side |
| LangGraph upgrades breaking checkpoints | Low | Med | Pin LangGraph version; checkpoint replay is opt-in (live mode works without replay) |
| False consensus heuristics miss real cases | Med | Med | Three regression fixtures + manual review of first month of debates; thresholds tunable |
| Subscription rate limits hit during big-bang day | Med | High | SubprocessPool surfaces 429s; retries with backoff; degrade by reducing `MAX_DEBATE_ROUNDS_DAILY` automatically on sustained 429s |
| Memory tree.json grows unbounded | Low | Med | `MEMORY_TREE_MAX_BYTES=200KB`; rebuild truncates summaries; per-branch caps |
| Korean tokenization recall gaps in FTS5 | Med | Low | Trigram tokenizer chosen specifically for this; integration test verifies recall; can swap to `streetwriters/sqlite-better-trigram` if recall <80% |
| Big-bang regression on existing SPEC items | Med | Critical | Verdict.report_content is byte-compatible with legacy ReportContent; nightly full-suite regression CI |

---

## 17. License Compatibility (Apache 2.0)

| Dependency | License | Compatible |
|---|---|---|
| LangGraph | MIT | ✓ |
| sse-starlette | BSD-3-Clause | ✓ |
| httpx | BSD-3-Clause | ✓ |
| rank_bm25 (fallback for FTS5 unavailable) | Apache 2.0 | ✓ |
| Multica | Apache 2.0 | ✓ (separate container; not statically linked) |
| SQLite FTS5 | Public Domain | ✓ |

`claude` and `codex` CLIs are user-installed binaries; their license terms apply to the user's local installation, not this repo.

---

## 18. Open Questions

These are deferred to implementation discovery and resolved in the implementation plan:

1. **Codex exec exact flags** — must verify `--output-format`, `--model`, stdin behavior against current Codex CLI; adapter design is robust to flag changes but exact strings unknown
2. **Multica HTTP API endpoints** — issue/comment paths are inferred from Multica's docs; will confirm against running instance during implementation
3. **LangGraph checkpoint persistence** — using LangGraph's built-in SQLite store vs writing a custom checkpointer (decision in implementation: prefer built-in unless schema clash)
4. **System prompt template language** — Jinja2 used elsewhere in this repo, so reusing; verify no escape conflicts with markdown content
5. **News pipeline Verdict shape** — does Editor/Publisher Verdict include `recommendations[]` or only `news_items[]`? (Probably only news_items; existing RPT-02 shape suggests no recs.) Decide in implementation against existing news flow

---

## 19. Implementation Phases (within this single spec/release)

The big-bang requirement does not mean parallel chaos. Within the single release, work is sequenced for safe incremental verification:

1. **Foundations**: SubprocessPool, ClaudeCodeProvider, CodexProvider, Provider tests
2. **Memory subsystem**: MarkdownMemoryStore, JSONTreeIndex, SQLiteFTS5Search, ingest atomicity, traversal
3. **Domain + DebateGraph**: LangGraph state graph, deterministic stub LLM for testing, in-memory unit tests
4. **Judge**: rule + LLM + false-consensus; regression fixtures
5. **Pipeline integration**: RunDailyDebate replaces legacy ClaudeNewsProvider call; Verdict→ReportContent compatibility verified by existing RPT tests
6. **News / global-news / weekly pipelines**: same pattern as daily
7. **SSE + DebateBus**: streaming endpoint + EventSource client
8. **UI new pages**: /agents, /agents/[role], /debate, /debate/[id], /memory
9. **Multica adapter**: HTTP client + webhook + docker-compose
10. **/multica UI + /settings extensions**
11. **Full E2E + regression sweep**

Each phase has a checkpoint: regression suite must remain green before moving on.

---

## 20. Acceptance Criteria Index

Full list of new and modified spec IDs (suitable for SPEC.md merge after design approval):

`AGENT-01..06` · `DEBATE-01..10` · `JUDGE-01..08` · `MEM-01..10` · `UI-09..18` · `SSE-01..04` · `MULTICA-01..08` · `BACK-01..07` · `CFG-06..09` · `DATA-04..07` · `TEST-01..05`

Plus all existing `PIPE-*`, `REC-*`, `RPT-*`, `RETRO-*`, `API-*`, `CFG-01..05`, `ERR-*`, `DATA-01..03` continue to pass unchanged ("zero regressions" — Q2 hard constraint).
