# Plan 2 — Debate Engine + Pipeline Integration

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the LangGraph-based multi-agent debate engine on top of Plan 1's foundations, and integrate it into all 4 pipelines (`daily`, `news`, `global-news`, `weekly`) **without breaking any existing acceptance criterion**.

**Architecture:** A new `CouncilNewsProvider` implements the existing `NewsProviderPort` and produces JSON output identical in shape to what `ClaudeNewsProvider` produces today. The four `generate_*_report` methods internally invoke pipeline-specific LangGraph `StateGraph` runs that orchestrate analyst/researcher/trader/risk/PM/judge agents through the providers from Plan 1. Switching the `get_news_provider()` factory swaps the entire LLM layer in one place — every downstream parser, renderer, repo, email, and UI continues unchanged.

**Tech Stack:** Python 3.11 · LangGraph 0.2+ · LangGraph SQLite checkpointer · Plan 1's `LLMProviderPort` / `MemoryStorePort`. No API keys (subscription CLIs only).

**Spec source:** [`docs/superpowers/specs/2026-05-25-multi-agent-council-design.md`](../specs/2026-05-25-multi-agent-council-design.md) — Sections 5 (Domain Model), 6 (Agents), 7 (Debate Flow), 8 (Judge). Acceptance: `AGENT-01..06`, `DEBATE-01..10`, `JUDGE-01..08`, `MEM-08` (auto-injection), `DATA-05`.

---

## Zero-Regression Strategy

The existing test suite (`PIPE-*`, `REC-*`, `RPT-*`, `RETRO-*`, `API-*`) consumes the JSON output of `news.generate_daily_report(...)` etc. New code must produce **byte-equivalent JSON shape** for those tests to keep passing. The contract is enforced by:

1. `CouncilNewsProvider` implements `NewsProviderPort` (same four method signatures, same `tuple[str, float]` return).
2. The JSON serializer (`verdict_to_report_json`) emits keys/types accepted by the existing `parse_report_content()` parser.
3. A new test `test_council_provider_output_parses_to_report_content` ensures round-trip compatibility.
4. CI runs the full existing test suite after each task.

---

## File Structure

### New files

```
backend/src/daily_scheduler/
├── domain/
│   ├── entities/
│   │   ├── agent.py                       # Agent, Role, BackendBinding
│   │   ├── debate.py                      # DebateGraph, Round, Speech, Verdict, ConsensusScore
│   │   └── debate_state.py                # DebateState (LangGraph state object)
│   └── ports/
│       └── agent_binding_repo.py          # AgentBindingRepositoryPort
├── application/
│   └── use_cases/
│       ├── run_daily_debate.py            # Builds + runs the daily LangGraph
│       ├── run_news_debate.py             # KR & Global news (parameterized)
│       ├── run_weekly_debate.py           # Sequential weekly (no debate loop)
│       ├── debate_engine.py               # Common helpers (state init, callback wiring)
│       └── memory_injection.py            # build_memory_context()
└── infrastructure/
    └── adapters/
        ├── council/
        │   ├── __init__.py
        │   ├── council_news_provider.py   # Implements NewsProviderPort
        │   ├── verdict_serializer.py      # Verdict → ReportContent-compatible JSON
        │   ├── prompt_templates.py        # System prompt loader (Jinja2)
        │   └── role_registry.py           # Role → default BackendBinding map
        ├── persistence/
        │   ├── agent_binding_repository.py
        │   ├── debate_repository.py
        │   └── (additions to models.py: agent_binding, debate, round, speech tables)
        └── debate/
            ├── __init__.py
            ├── analyst_node.py            # LangGraph node — parallel analyst pool
            ├── bull_bear_nodes.py         # LangGraph nodes — debaters
            ├── judge_node.py              # LangGraph node — hybrid judge
            ├── decision_nodes.py          # LangGraph nodes — Trader/Risk/PM
            ├── editor_publisher_nodes.py  # LangGraph nodes — news pipelines
            ├── graph_builder.py           # build_daily_graph(), build_news_graph(), build_weekly_graph()
            └── llm_router.py              # Resolves Role → LLMProviderPort
```

### New prompt templates

```
backend/src/daily_scheduler/templates/prompts/agents/
├── kr_fundamentals.j2
├── us_fundamentals.j2
├── kr_technical.j2
├── us_technical.j2
├── news_sentiment.j2
├── bull.j2
├── bear.j2
├── judge.j2
├── trader.j2
├── risk_mgmt.j2
├── portfolio_mgr.j2
├── editor.j2
├── publisher.j2
├── perf_analyst.j2
└── lessons_researcher.j2
```

Each template renders with: `pipeline`, `market_data`, `screening` (daily only), `retrospective`, `memory_context` (auto-injected), and role-specific inputs (e.g., `analyst_reports` for bull/bear, `prior_rounds` for round 2+, `consensus_score` for trader).

### New tests

```
backend/tests/
├── test_agent_entity.py
├── test_debate_entity.py
├── test_debate_state.py
├── test_agent_binding_repo.py
├── test_role_registry.py
├── test_llm_router.py
├── test_analyst_node.py
├── test_bull_bear_nodes.py
├── test_judge_node.py
├── test_decision_nodes.py
├── test_editor_publisher_nodes.py
├── test_graph_builder.py
├── test_verdict_serializer.py
├── test_council_news_provider.py
├── test_memory_injection.py
├── test_run_daily_debate.py
├── test_run_news_debate.py
├── test_run_weekly_debate.py
├── test_recommendation_debate_link.py       # ORM migration test
├── fixtures/
│   ├── judge_clear_consensus.json
│   ├── judge_clear_dissent.json
│   └── judge_false_consensus.json
```

### Modified files

- `backend/pyproject.toml` — add `langgraph>=0.2`, `langgraph-checkpoint-sqlite>=2.0`
- `backend/src/daily_scheduler/infrastructure/adapters/persistence/models.py` — add columns (`debate_id`, `memory_node_id` on `recommendations`) + new tables
- `backend/src/daily_scheduler/infrastructure/dependencies.py` — swap `get_news_provider()` to return `CouncilNewsProvider`
- `backend/src/daily_scheduler/application/use_cases/check_recommendations.py` — call `memory_store.update_outcome` when recommendation closes
- `backend/src/daily_scheduler/templates/prompts/` — keep legacy 4 templates untouched (used as fallback / reference)

---

## Task 1: Add LangGraph dependencies

**Files:** Modify `backend/pyproject.toml`

- [ ] **Step 1:** Edit `backend/pyproject.toml`, appending to `dependencies`:
  ```toml
      "langgraph>=0.2",
      "langgraph-checkpoint-sqlite>=2.0",
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv sync
  ```
  Expected: resolves langgraph + langgraph-checkpoint-sqlite and their transitive deps (`langchain-core`, etc.).

- [ ] **Step 3:** Verify import:
  ```bash
  cd backend && uv run python -c "from langgraph.graph import StateGraph, START, END; from langgraph.checkpoint.sqlite import SqliteSaver; print('ok')"
  ```
  Expected: prints `ok`.

- [ ] **Step 4:** Commit:
  ```bash
  git add backend/pyproject.toml backend/uv.lock
  git commit -m "chore: add langgraph + sqlite checkpointer for debate engine"
  ```

---

## Task 2: Agent / Role / BackendBinding entities

**Files:**
- Create: `backend/src/daily_scheduler/domain/entities/agent.py`
- Test: `backend/tests/test_agent_entity.py`

- [ ] **Step 1: Write failing test** — `backend/tests/test_agent_entity.py`:
  ```python
  """Tests for Agent, Role, BackendBinding entities."""
  from __future__ import annotations

  import pytest

  from daily_scheduler.domain.entities.agent import (
      Agent,
      BackendBinding,
      Provider,
      Role,
  )


  def test_role_enum_has_all_pipeline_roles() -> None:
      expected = {
          "KR_FUNDAMENTALS", "US_FUNDAMENTALS", "KR_TECHNICAL", "US_TECHNICAL",
          "NEWS_SENT", "BULL", "BEAR", "JUDGE",
          "TRADER", "RISK_MGMT", "PORTFOLIO_MGR",
          "EDITOR", "PUBLISHER",
          "PERF_ANALYST", "LESSONS_RESEARCHER",
      }
      assert {r.name for r in Role} == expected


  def test_provider_enum() -> None:
      assert Provider.CLAUDE_CODE.value == "claude-code"
      assert Provider.CODEX.value == "codex"


  def test_backend_binding_defaults() -> None:
      b = BackendBinding(provider=Provider.CLAUDE_CODE, model="opus")
      assert b.provider is Provider.CLAUDE_CODE
      assert b.model == "opus"
      assert b.system_prompt_override is None
      assert b.timeout_s == 600


  def test_agent_dataclass_carries_role_and_binding() -> None:
      a = Agent(
          role=Role.BULL,
          binding=BackendBinding(provider=Provider.CLAUDE_CODE, model="opus"),
          display_name="Bull Researcher",
      )
      assert a.role is Role.BULL
      assert a.binding.provider is Provider.CLAUDE_CODE
      assert a.display_name == "Bull Researcher"


  def test_role_pipelines_membership() -> None:
      from daily_scheduler.domain.entities.agent import roles_for_pipeline
      assert set(roles_for_pipeline("daily")) == {
          Role.KR_FUNDAMENTALS, Role.US_FUNDAMENTALS,
          Role.KR_TECHNICAL, Role.US_TECHNICAL, Role.NEWS_SENT,
          Role.BULL, Role.BEAR, Role.JUDGE,
          Role.TRADER, Role.RISK_MGMT, Role.PORTFOLIO_MGR,
      }
      assert set(roles_for_pipeline("news")) == {
          Role.NEWS_SENT, Role.KR_TECHNICAL,
          Role.EDITOR, Role.PUBLISHER, Role.JUDGE,
      }
      assert set(roles_for_pipeline("global-news")) == {
          Role.NEWS_SENT, Role.US_TECHNICAL,
          Role.EDITOR, Role.PUBLISHER, Role.JUDGE,
      }
      assert set(roles_for_pipeline("weekly")) == {
          Role.PERF_ANALYST, Role.LESSONS_RESEARCHER, Role.PORTFOLIO_MGR,
      }
      with pytest.raises(KeyError):
          roles_for_pipeline("unknown")
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_agent_entity.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/domain/entities/agent.py`:
  ```python
  """Agent / Role / BackendBinding — the agent-side domain model."""
  from __future__ import annotations

  from dataclasses import dataclass
  from enum import StrEnum


  class Role(StrEnum):
      KR_FUNDAMENTALS = "kr_fundamentals"
      US_FUNDAMENTALS = "us_fundamentals"
      KR_TECHNICAL = "kr_technical"
      US_TECHNICAL = "us_technical"
      NEWS_SENT = "news_sent"
      BULL = "bull"
      BEAR = "bear"
      JUDGE = "judge"
      TRADER = "trader"
      RISK_MGMT = "risk_mgmt"
      PORTFOLIO_MGR = "portfolio_mgr"
      EDITOR = "editor"
      PUBLISHER = "publisher"
      PERF_ANALYST = "perf_analyst"
      LESSONS_RESEARCHER = "lessons_researcher"


  class Provider(StrEnum):
      CLAUDE_CODE = "claude-code"
      CODEX = "codex"


  @dataclass(frozen=True, slots=True)
  class BackendBinding:
      provider: Provider
      model: str
      system_prompt_override: str | None = None
      timeout_s: int = 600


  @dataclass(frozen=True, slots=True)
  class Agent:
      role: Role
      binding: BackendBinding
      display_name: str
      description: str = ""


  _PIPELINE_ROLES: dict[str, tuple[Role, ...]] = {
      "daily": (
          Role.KR_FUNDAMENTALS, Role.US_FUNDAMENTALS,
          Role.KR_TECHNICAL, Role.US_TECHNICAL, Role.NEWS_SENT,
          Role.BULL, Role.BEAR, Role.JUDGE,
          Role.TRADER, Role.RISK_MGMT, Role.PORTFOLIO_MGR,
      ),
      "news": (
          Role.NEWS_SENT, Role.KR_TECHNICAL,
          Role.EDITOR, Role.PUBLISHER, Role.JUDGE,
      ),
      "global-news": (
          Role.NEWS_SENT, Role.US_TECHNICAL,
          Role.EDITOR, Role.PUBLISHER, Role.JUDGE,
      ),
      "weekly": (
          Role.PERF_ANALYST, Role.LESSONS_RESEARCHER, Role.PORTFOLIO_MGR,
      ),
  }


  def roles_for_pipeline(pipeline: str) -> tuple[Role, ...]:
      return _PIPELINE_ROLES[pipeline]
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_agent_entity.py -v
  ```
  Expected: 5 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/domain/entities/agent.py backend/tests/test_agent_entity.py
  git commit -m "feat(domain): add Agent, Role, BackendBinding, roles_for_pipeline"
  ```

---

## Task 3: Debate / Round / Speech / Verdict / ConsensusScore entities

**Files:**
- Create: `backend/src/daily_scheduler/domain/entities/debate.py`
- Test: `backend/tests/test_debate_entity.py`

- [ ] **Step 1: Write failing test** — `backend/tests/test_debate_entity.py`:
  ```python
  """Tests for debate-side domain entities."""
  from __future__ import annotations

  from datetime import datetime

  import pytest

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.entities.debate import (
      ConsensusScore,
      DebateGraph,
      DebateState,
      Round,
      Speech,
      Verdict,
  )


  def test_debate_state_enum() -> None:
      assert DebateState.RUNNING.value == "RUNNING"
      assert DebateState.CONVERGED.value == "CONVERGED"
      assert DebateState.MAX_ROUNDS_DISSENT.value == "MAX_ROUNDS_DISSENT"
      assert DebateState.FAILED.value == "FAILED"


  def test_speech_carries_role_and_text() -> None:
      s = Speech(
          agent_role=Role.BULL,
          text="hello",
          structured_json={"direction": "BUY"},
          tokens_in=10, tokens_out=2,
          latency_ms=100,
          cli_command_hash="abc123",
      )
      assert s.agent_role is Role.BULL
      assert s.structured_json["direction"] == "BUY"


  def test_consensus_score_holds_both_dimensions() -> None:
      c = ConsensusScore(
          rule_score=0.8, llm_score=0.75,
          false_consensus=False,
          next_round_questions=["q1", "q2"],
          dimensions={"direction": 1.0, "ticker_overlap": 0.6},
      )
      assert c.rule_score == 0.8
      assert c.converged(rule_threshold=0.75, llm_threshold=0.70)


  def test_consensus_score_blocks_on_false_consensus() -> None:
      c = ConsensusScore(
          rule_score=1.0, llm_score=1.0,
          false_consensus=True,
          next_round_questions=[],
          dimensions={},
      )
      # Both scores pass but false_consensus blocks
      assert c.converged(rule_threshold=0.75, llm_threshold=0.70) is False


  def test_round_carries_two_speeches_and_score() -> None:
      bull = Speech(agent_role=Role.BULL, text="b", structured_json={},
                   tokens_in=0, tokens_out=0, latency_ms=0, cli_command_hash="")
      bear = Speech(agent_role=Role.BEAR, text="r", structured_json={},
                   tokens_in=0, tokens_out=0, latency_ms=0, cli_command_hash="")
      score = ConsensusScore(rule_score=0.5, llm_score=0.5,
                              false_consensus=False, next_round_questions=[],
                              dimensions={})
      r = Round(index=0, bull_speech=bull, bear_speech=bear, judge_score=score)
      assert r.index == 0
      assert r.converged is False


  def test_verdict_links_to_debate_and_recommendations() -> None:
      v = Verdict(
          debate_id="d1",
          consensus=DebateState.CONVERGED,
          report_content_json={"market_summary": "x"},
          recommendation_dicts=[{"ticker": "005930", "direction": "LONG"}],
      )
      assert v.debate_id == "d1"
      assert v.consensus is DebateState.CONVERGED
      assert v.report_content_json["market_summary"] == "x"


  def test_debate_graph_aggregates_everything() -> None:
      g = DebateGraph(
          id="d1", pipeline="daily", state=DebateState.RUNNING,
          rounds=[], analyst_reports=[], verdict=None,
          started_at=datetime.now(), ended_at=None,
          triggered_by="scheduler",
      )
      assert g.id == "d1"
      assert g.state is DebateState.RUNNING
      assert g.rounds == []
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_debate_entity.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/domain/entities/debate.py`:
  ```python
  """Debate-side domain entities: DebateGraph, Round, Speech, Verdict, ConsensusScore."""
  from __future__ import annotations

  from dataclasses import dataclass, field
  from datetime import datetime
  from enum import StrEnum
  from typing import Any

  from daily_scheduler.domain.entities.agent import Role


  class DebateState(StrEnum):
      RUNNING = "RUNNING"
      CONVERGED = "CONVERGED"
      MAX_ROUNDS_DISSENT = "MAX_ROUNDS_DISSENT"
      FAILED = "FAILED"


  @dataclass(frozen=True, slots=True)
  class Speech:
      agent_role: Role
      text: str
      structured_json: dict[str, Any]
      tokens_in: int
      tokens_out: int
      latency_ms: int
      cli_command_hash: str


  @dataclass(frozen=True, slots=True)
  class ConsensusScore:
      rule_score: float
      llm_score: float
      false_consensus: bool
      next_round_questions: list[str]
      dimensions: dict[str, float]

      def converged(self, *, rule_threshold: float, llm_threshold: float) -> bool:
          if self.false_consensus:
              return False
          return self.rule_score >= rule_threshold and self.llm_score >= llm_threshold


  @dataclass(frozen=True, slots=True)
  class Round:
      index: int
      bull_speech: Speech
      bear_speech: Speech
      judge_score: ConsensusScore

      @property
      def converged(self) -> bool:
          # Convergence is determined by the engine using thresholds; this is a
          # convenience check assuming default thresholds.
          return self.judge_score.converged(rule_threshold=0.75, llm_threshold=0.70)


  @dataclass(frozen=True, slots=True)
  class Verdict:
      debate_id: str
      consensus: DebateState
      report_content_json: dict[str, Any]
      recommendation_dicts: list[dict[str, Any]]


  @dataclass
  class DebateGraph:
      id: str
      pipeline: str
      state: DebateState
      rounds: list[Round]
      analyst_reports: list[dict[str, Any]]
      verdict: Verdict | None
      started_at: datetime
      ended_at: datetime | None
      triggered_by: str  # "scheduler" | "manual" | "multica"
      error: str | None = None
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_debate_entity.py -v
  ```
  Expected: 7 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/domain/entities/debate.py backend/tests/test_debate_entity.py
  git commit -m "feat(domain): add Debate/Round/Speech/Verdict/ConsensusScore entities"
  ```

---

## Task 4: Persistence — agent_binding / debate / round / speech tables

**Files:**
- Modify: `backend/src/daily_scheduler/infrastructure/adapters/persistence/models.py`
- Modify: `backend/src/daily_scheduler/database.py` (init_database picks up new tables automatically via Base.metadata)
- Test: `backend/tests/test_debate_models.py`

- [ ] **Step 1: Write failing test** — `backend/tests/test_debate_models.py`:
  ```python
  """Tests for new ORM models supporting the debate engine."""
  from __future__ import annotations

  from datetime import datetime

  import pytest
  from sqlalchemy import create_engine
  from sqlalchemy.orm import Session

  from daily_scheduler.database import Base
  from daily_scheduler.infrastructure.adapters.persistence.models import (
      AgentBindingModel,
      DebateModel,
      RecommendationModel,
      RoundModel,
      SpeechModel,
  )


  @pytest.fixture
  def session():
      eng = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(eng)
      with Session(eng) as s:
          yield s


  def test_agent_binding_row(session) -> None:
      row = AgentBindingModel(
          role="bull",
          provider="claude-code",
          model="opus",
          system_prompt_override=None,
          timeout_s=600,
          updated_at=datetime.now(),
      )
      session.add(row)
      session.commit()
      assert session.get(AgentBindingModel, "bull").model == "opus"


  def test_debate_row(session) -> None:
      now = datetime.now()
      d = DebateModel(
          id="d1", pipeline="daily", state="RUNNING",
          started_at=now, ended_at=None,
          triggered_by="scheduler",
          verdict_json=None, error=None,
      )
      session.add(d)
      session.commit()
      assert session.get(DebateModel, "d1").pipeline == "daily"


  def test_round_and_speech_rows(session) -> None:
      now = datetime.now()
      d = DebateModel(id="d2", pipeline="daily", state="RUNNING",
                     started_at=now, ended_at=None, triggered_by="scheduler",
                     verdict_json=None, error=None)
      session.add(d)
      session.commit()

      r = RoundModel(
          id="r1", debate_id="d2", idx=0,
          rule_score=0.8, llm_score=0.7,
          false_consensus=False, converged=True,
          dimensions_json={"direction": 1.0},
          next_round_questions_json=[],
          created_at=now,
      )
      session.add(r)
      session.commit()

      s = SpeechModel(
          id="s1", debate_id="d2", round_id="r1",
          agent_role="bull", text="hello",
          structured_json={"direction": "BUY"},
          tokens_in=10, tokens_out=2,
          latency_ms=100, cli_command_hash="abc",
          created_at=now,
      )
      session.add(s)
      session.commit()
      assert session.get(SpeechModel, "s1").agent_role == "bull"


  def test_recommendation_has_debate_id_and_memory_node_id(session) -> None:
      now = datetime.now()
      # Smoke test: column exists and accepts NULL + str
      rec = RecommendationModel(
          report_id=1, ticker="005930", name="Samsung Electronics",
          market="KOSPI", direction="LONG", timeframe="DAY",
          entry_price=70000.0, target_price=75000.0, stop_loss=68000.0,
          debate_id="d1", memory_node_id="m1",
      )
      session.add(rec)
      # We don't have a real report row, but the column-level smoke test
      # is enough to ensure the migration exists.
      assert rec.debate_id == "d1"
      assert rec.memory_node_id == "m1"
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_debate_models.py -v
  ```
  Expected: ImportError (AgentBindingModel etc. not defined).

- [ ] **Step 3:** Append to `backend/src/daily_scheduler/infrastructure/adapters/persistence/models.py`:
  ```python
  # --- Multi-agent council ORM (Plan 2) ---

  from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text


  class AgentBindingModel(Base):
      __tablename__ = "agent_binding"

      role: Mapped[str] = mapped_column(String, primary_key=True)
      provider: Mapped[str] = mapped_column(String, nullable=False)
      model: Mapped[str] = mapped_column(String, nullable=False)
      system_prompt_override: Mapped[str | None] = mapped_column(Text, nullable=True)
      timeout_s: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
      updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


  class DebateModel(Base):
      __tablename__ = "debate"

      id: Mapped[str] = mapped_column(String, primary_key=True)
      pipeline: Mapped[str] = mapped_column(String, nullable=False, index=True)
      state: Mapped[str] = mapped_column(String, nullable=False, index=True)
      started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
      ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
      triggered_by: Mapped[str] = mapped_column(String, nullable=False)
      verdict_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
      error: Mapped[str | None] = mapped_column(Text, nullable=True)


  class RoundModel(Base):
      __tablename__ = "round"

      id: Mapped[str] = mapped_column(String, primary_key=True)
      debate_id: Mapped[str] = mapped_column(String, ForeignKey("debate.id"), nullable=False, index=True)
      idx: Mapped[int] = mapped_column(Integer, nullable=False)
      rule_score: Mapped[float] = mapped_column(Float, nullable=False)
      llm_score: Mapped[float] = mapped_column(Float, nullable=False)
      false_consensus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
      converged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
      dimensions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
      next_round_questions_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
      created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


  class SpeechModel(Base):
      __tablename__ = "speech"

      id: Mapped[str] = mapped_column(String, primary_key=True)
      debate_id: Mapped[str] = mapped_column(String, ForeignKey("debate.id"), nullable=False, index=True)
      round_id: Mapped[str | None] = mapped_column(String, ForeignKey("round.id"), nullable=True, index=True)
      agent_role: Mapped[str] = mapped_column(String, nullable=False, index=True)
      text: Mapped[str] = mapped_column(Text, nullable=False)
      structured_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
      tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
      tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
      latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
      cli_command_hash: Mapped[str] = mapped_column(String, nullable=False, default="")
      created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
  ```

- [ ] **Step 4:** In the same `models.py`, locate the existing `class RecommendationModel(Base):` and **add two new nullable columns** at the bottom of the column list (before `created_at` if present, or just at the end):
  ```python
      debate_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
      memory_node_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
  ```

- [ ] **Step 5:** Run:
  ```bash
  cd backend && uv run pytest tests/test_debate_models.py -v
  ```
  Expected: 4 passed.

- [ ] **Step 6:** Run the full suite to confirm no regression on existing recommendation tests:
  ```bash
  cd backend && uv run pytest -v 2>&1 | tail -5
  ```
  Expected: all green.

- [ ] **Step 7:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/persistence/models.py backend/tests/test_debate_models.py
  git commit -m "feat(persistence): add agent_binding/debate/round/speech tables + debate_id/memory_node_id on recommendation"
  ```

---

## Task 5: AgentBindingRepository

**Files:**
- Create: `backend/src/daily_scheduler/domain/ports/agent_binding_repo.py`
- Create: `backend/src/daily_scheduler/infrastructure/adapters/persistence/agent_binding_repository.py`
- Test: `backend/tests/test_agent_binding_repo.py`

- [ ] **Step 1: Write failing test** — `backend/tests/test_agent_binding_repo.py`:
  ```python
  """Tests for AgentBindingRepository (port + SQLAlchemy adapter)."""
  from __future__ import annotations

  import pytest
  from sqlalchemy import create_engine
  from sqlalchemy.orm import Session

  from daily_scheduler.database import Base
  from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role
  from daily_scheduler.infrastructure.adapters.persistence.agent_binding_repository import (
      SQLAlchemyAgentBindingRepository,
  )


  @pytest.fixture
  def repo():
      eng = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(eng)
      with Session(eng) as s:
          yield SQLAlchemyAgentBindingRepository(s)


  def test_get_returns_none_when_no_override(repo) -> None:
      assert repo.get(Role.BULL) is None


  def test_upsert_then_get(repo) -> None:
      b = BackendBinding(provider=Provider.CODEX, model="gpt-5-codex", timeout_s=300)
      repo.upsert(Role.JUDGE, b)
      fetched = repo.get(Role.JUDGE)
      assert fetched is not None
      assert fetched.provider is Provider.CODEX
      assert fetched.model == "gpt-5-codex"
      assert fetched.timeout_s == 300


  def test_upsert_overwrites(repo) -> None:
      b1 = BackendBinding(provider=Provider.CLAUDE_CODE, model="sonnet")
      b2 = BackendBinding(provider=Provider.CLAUDE_CODE, model="opus")
      repo.upsert(Role.TRADER, b1)
      repo.upsert(Role.TRADER, b2)
      fetched = repo.get(Role.TRADER)
      assert fetched.model == "opus"


  def test_delete_removes(repo) -> None:
      b = BackendBinding(provider=Provider.CLAUDE_CODE, model="opus")
      repo.upsert(Role.BULL, b)
      repo.delete(Role.BULL)
      assert repo.get(Role.BULL) is None


  def test_list_all(repo) -> None:
      repo.upsert(Role.BULL, BackendBinding(provider=Provider.CLAUDE_CODE, model="opus"))
      repo.upsert(Role.BEAR, BackendBinding(provider=Provider.CLAUDE_CODE, model="opus"))
      all_bindings = dict(repo.list_all())
      assert Role.BULL in all_bindings
      assert Role.BEAR in all_bindings
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_agent_binding_repo.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create the port `backend/src/daily_scheduler/domain/ports/agent_binding_repo.py`:
  ```python
  """Port for the agent_binding store."""
  from __future__ import annotations

  from collections.abc import Iterator
  from typing import Protocol

  from daily_scheduler.domain.entities.agent import BackendBinding, Role


  class AgentBindingRepositoryPort(Protocol):
      def get(self, role: Role) -> BackendBinding | None: ...
      def upsert(self, role: Role, binding: BackendBinding) -> None: ...
      def delete(self, role: Role) -> None: ...
      def list_all(self) -> Iterator[tuple[Role, BackendBinding]]: ...
  ```

  Create the adapter `backend/src/daily_scheduler/infrastructure/adapters/persistence/agent_binding_repository.py`:
  ```python
  """SQLAlchemy adapter for AgentBindingRepositoryPort."""
  from __future__ import annotations

  from collections.abc import Iterator
  from datetime import datetime

  from sqlalchemy.orm import Session

  from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role
  from daily_scheduler.infrastructure.adapters.persistence.models import (
      AgentBindingModel,
  )


  class SQLAlchemyAgentBindingRepository:
      def __init__(self, session: Session) -> None:
          self._s = session

      def get(self, role: Role) -> BackendBinding | None:
          row = self._s.get(AgentBindingModel, role.value)
          if row is None:
              return None
          return self._row_to_binding(row)

      def upsert(self, role: Role, binding: BackendBinding) -> None:
          row = self._s.get(AgentBindingModel, role.value)
          now = datetime.now()
          if row is None:
              row = AgentBindingModel(
                  role=role.value,
                  provider=binding.provider.value,
                  model=binding.model,
                  system_prompt_override=binding.system_prompt_override,
                  timeout_s=binding.timeout_s,
                  updated_at=now,
              )
              self._s.add(row)
          else:
              row.provider = binding.provider.value
              row.model = binding.model
              row.system_prompt_override = binding.system_prompt_override
              row.timeout_s = binding.timeout_s
              row.updated_at = now
          self._s.commit()

      def delete(self, role: Role) -> None:
          row = self._s.get(AgentBindingModel, role.value)
          if row is not None:
              self._s.delete(row)
              self._s.commit()

      def list_all(self) -> Iterator[tuple[Role, BackendBinding]]:
          for row in self._s.query(AgentBindingModel).all():
              yield Role(row.role), self._row_to_binding(row)

      @staticmethod
      def _row_to_binding(row: AgentBindingModel) -> BackendBinding:
          return BackendBinding(
              provider=Provider(row.provider),
              model=row.model,
              system_prompt_override=row.system_prompt_override,
              timeout_s=row.timeout_s,
          )
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_agent_binding_repo.py -v
  ```
  Expected: 5 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/domain/ports/agent_binding_repo.py backend/src/daily_scheduler/infrastructure/adapters/persistence/agent_binding_repository.py backend/tests/test_agent_binding_repo.py
  git commit -m "feat(persistence): add AgentBindingRepository (port + SQLAlchemy adapter)"
  ```

---

## Task 6: RoleRegistry (default bindings) + LLM Router

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/council/__init__.py`
- Create: `backend/src/daily_scheduler/infrastructure/adapters/council/role_registry.py`
- Create: `backend/src/daily_scheduler/infrastructure/adapters/debate/__init__.py`
- Create: `backend/src/daily_scheduler/infrastructure/adapters/debate/llm_router.py`
- Test: `backend/tests/test_role_registry.py`
- Test: `backend/tests/test_llm_router.py`

- [ ] **Step 1: Write failing tests** — `backend/tests/test_role_registry.py`:
  ```python
  """Tests for default role → BackendBinding map."""
  from __future__ import annotations

  from daily_scheduler.domain.entities.agent import Provider, Role
  from daily_scheduler.infrastructure.adapters.council.role_registry import (
      default_binding_for,
      tools_for_role,
  )


  def test_analyst_defaults_use_claude_code_with_websearch_tools() -> None:
      for role in (Role.KR_FUNDAMENTALS, Role.US_FUNDAMENTALS,
                   Role.KR_TECHNICAL, Role.US_TECHNICAL, Role.NEWS_SENT):
          b = default_binding_for(role)
          assert b.provider is Provider.CLAUDE_CODE
          assert "WebSearch" in tools_for_role(role)


  def test_judge_default_uses_codex() -> None:
      b = default_binding_for(Role.JUDGE)
      assert b.provider is Provider.CODEX


  def test_decision_roles_use_claude_code_no_tools() -> None:
      for role in (Role.TRADER, Role.RISK_MGMT, Role.PORTFOLIO_MGR):
          b = default_binding_for(role)
          assert b.provider is Provider.CLAUDE_CODE
          assert tools_for_role(role) == []


  def test_news_roles() -> None:
      for role in (Role.EDITOR, Role.PUBLISHER):
          b = default_binding_for(role)
          assert b.provider is Provider.CLAUDE_CODE
  ```

  And `backend/tests/test_llm_router.py`:
  ```python
  """Tests for LLM Router — resolves Role → LLMProviderPort respecting overrides."""
  from __future__ import annotations

  from unittest.mock import MagicMock

  import pytest

  from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


  def test_router_uses_default_when_no_override() -> None:
      claude = MagicMock(name="claude_code")
      codex = MagicMock(name="codex")
      binding_repo = MagicMock()
      binding_repo.get = MagicMock(return_value=None)
      router = LLMRouter(
          claude_code=claude, codex=codex, binding_repo=binding_repo,
      )
      provider, binding = router.resolve(Role.JUDGE)
      assert provider is codex
      assert binding.provider is Provider.CODEX


  def test_router_uses_override_when_present() -> None:
      claude = MagicMock()
      codex = MagicMock()
      override = BackendBinding(provider=Provider.CODEX, model="gpt-5-codex", timeout_s=120)
      binding_repo = MagicMock()
      binding_repo.get = MagicMock(return_value=override)
      router = LLMRouter(
          claude_code=claude, codex=codex, binding_repo=binding_repo,
      )
      provider, binding = router.resolve(Role.BULL)
      assert provider is codex  # override flipped to codex
      assert binding.timeout_s == 120
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_role_registry.py tests/test_llm_router.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/council/__init__.py` (empty docstring).

  Create `backend/src/daily_scheduler/infrastructure/adapters/council/role_registry.py`:
  ```python
  """Default BackendBinding and tool list per Role."""
  from __future__ import annotations

  from daily_scheduler.constants import CLI_TIMEOUT_ANALYST_S, CLI_TIMEOUT_DEBATE_S, CLI_TIMEOUT_DECISION_S, CLI_TIMEOUT_JUDGE_S
  from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role

  _DEFAULTS: dict[Role, BackendBinding] = {
      Role.KR_FUNDAMENTALS: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_ANALYST_S),
      Role.US_FUNDAMENTALS: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_ANALYST_S),
      Role.KR_TECHNICAL: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_ANALYST_S),
      Role.US_TECHNICAL: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_ANALYST_S),
      Role.NEWS_SENT: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_ANALYST_S),
      Role.BULL: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_DEBATE_S),
      Role.BEAR: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_DEBATE_S),
      Role.JUDGE: BackendBinding(provider=Provider.CODEX, model="gpt-5-codex", timeout_s=CLI_TIMEOUT_JUDGE_S),
      Role.TRADER: BackendBinding(provider=Provider.CLAUDE_CODE, model="sonnet", timeout_s=CLI_TIMEOUT_DECISION_S),
      Role.RISK_MGMT: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_DECISION_S),
      Role.PORTFOLIO_MGR: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_DECISION_S),
      Role.EDITOR: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_DEBATE_S),
      Role.PUBLISHER: BackendBinding(provider=Provider.CLAUDE_CODE, model="opus", timeout_s=CLI_TIMEOUT_DEBATE_S),
      Role.PERF_ANALYST: BackendBinding(provider=Provider.CLAUDE_CODE, model="sonnet", timeout_s=CLI_TIMEOUT_DECISION_S),
      Role.LESSONS_RESEARCHER: BackendBinding(provider=Provider.CLAUDE_CODE, model="sonnet", timeout_s=CLI_TIMEOUT_DECISION_S),
  }

  _TOOLS: dict[Role, list[str]] = {
      Role.KR_FUNDAMENTALS: ["WebSearch", "WebFetch"],
      Role.US_FUNDAMENTALS: ["WebSearch", "WebFetch"],
      Role.KR_TECHNICAL: ["WebSearch", "WebFetch"],
      Role.US_TECHNICAL: ["WebSearch", "WebFetch"],
      Role.NEWS_SENT: ["WebSearch", "WebFetch"],
      Role.BULL: ["WebSearch"],
      Role.BEAR: ["WebSearch"],
      Role.EDITOR: ["WebSearch"],
      Role.PUBLISHER: ["WebSearch"],
  }


  def default_binding_for(role: Role) -> BackendBinding:
      return _DEFAULTS[role]


  def tools_for_role(role: Role) -> list[str]:
      return list(_TOOLS.get(role, []))
  ```

  Create `backend/src/daily_scheduler/infrastructure/adapters/debate/__init__.py` (empty docstring).

  Create `backend/src/daily_scheduler/infrastructure/adapters/debate/llm_router.py`:
  ```python
  """LLMRouter — resolves Role → (LLMProviderPort, BackendBinding) respecting overrides."""
  from __future__ import annotations

  from dataclasses import dataclass

  from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role
  from daily_scheduler.domain.ports.agent_binding_repo import AgentBindingRepositoryPort
  from daily_scheduler.domain.ports.llm_provider import LLMProviderPort
  from daily_scheduler.infrastructure.adapters.council.role_registry import (
      default_binding_for,
  )


  @dataclass(frozen=True, slots=True)
  class LLMRouter:
      claude_code: LLMProviderPort
      codex: LLMProviderPort
      binding_repo: AgentBindingRepositoryPort

      def resolve(self, role: Role) -> tuple[LLMProviderPort, BackendBinding]:
          binding = self.binding_repo.get(role) or default_binding_for(role)
          if binding.provider is Provider.CODEX:
              return self.codex, binding
          return self.claude_code, binding
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_role_registry.py tests/test_llm_router.py -v
  ```
  Expected: 5 passed (4 registry + 2 router = wait, total 6).

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/council/ backend/src/daily_scheduler/infrastructure/adapters/debate/ backend/tests/test_role_registry.py backend/tests/test_llm_router.py
  git commit -m "feat(council): add RoleRegistry defaults + LLMRouter"
  ```

---

## Task 7: Analyst node (parallel)

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/debate/analyst_node.py`
- Test: `backend/tests/test_analyst_node.py`

- [ ] **Step 1: Write failing test** — `backend/tests/test_analyst_node.py`:
  ```python
  """Tests for the parallel analyst node."""
  from __future__ import annotations

  import json
  from unittest.mock import AsyncMock, MagicMock

  import pytest

  from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role
  from daily_scheduler.domain.ports.llm_provider import LLMResult
  from daily_scheduler.infrastructure.adapters.debate.analyst_node import (
      run_analyst_pool,
  )


  def _result_for(role: str) -> LLMResult:
      return LLMResult(
          text=json.dumps({"role": role, "top_picks": ["005930"]}),
          model="opus", provider="claude-code",
          tokens_in=0, tokens_out=0, latency_ms=10, command_hash="abc",
      )


  @pytest.mark.asyncio
  async def test_run_analyst_pool_calls_each_role_in_parallel() -> None:
      claude = MagicMock()
      claude.submit = AsyncMock(side_effect=lambda prompt, **kw: _result_for(prompt[:20]))
      codex = MagicMock()
      binding_repo = MagicMock()
      binding_repo.get = MagicMock(return_value=None)
      from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter
      router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

      analyst_roles = [
          Role.KR_FUNDAMENTALS, Role.US_FUNDAMENTALS,
          Role.KR_TECHNICAL, Role.US_TECHNICAL, Role.NEWS_SENT,
      ]
      results = await run_analyst_pool(
          analyst_roles=analyst_roles,
          router=router,
          render_prompt=lambda role, ctx: f"prompt for {role.value}",
          context={"date": "2026-05-25"},
      )
      assert len(results) == 5
      assert claude.submit.call_count == 5
      for r in results:
          assert "role" in r
          assert "top_picks" in r


  @pytest.mark.asyncio
  async def test_analyst_non_json_response_kept_as_text() -> None:
      claude = MagicMock()
      claude.submit = AsyncMock(return_value=LLMResult(
          text="not json", model="opus", provider="claude-code",
          tokens_in=0, tokens_out=0, latency_ms=10, command_hash="abc",
      ))
      codex = MagicMock()
      binding_repo = MagicMock()
      binding_repo.get = MagicMock(return_value=None)
      from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter
      router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

      results = await run_analyst_pool(
          analyst_roles=[Role.KR_FUNDAMENTALS],
          router=router,
          render_prompt=lambda r, c: "p",
          context={},
      )
      assert len(results) == 1
      assert results[0]["raw_text"] == "not json"
      assert results[0]["role"] == "kr_fundamentals"
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_analyst_node.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/debate/analyst_node.py`:
  ```python
  """Parallel analyst pool — runs N analyst roles concurrently via the LLM pool."""
  from __future__ import annotations

  import asyncio
  import json
  import logging
  from collections.abc import Callable
  from typing import Any

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.infrastructure.adapters.council.role_registry import (
      tools_for_role,
  )
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

  logger = logging.getLogger(__name__)


  async def run_analyst_pool(
      *,
      analyst_roles: list[Role],
      router: LLMRouter,
      render_prompt: Callable[[Role, dict[str, Any]], str],
      context: dict[str, Any],
  ) -> list[dict[str, Any]]:
      """Run all analyst roles in parallel. Returns list of structured dicts."""

      async def _one(role: Role) -> dict[str, Any]:
          provider, binding = router.resolve(role)
          prompt = render_prompt(role, context)
          tools = tools_for_role(role)
          try:
              result = await provider.submit(
                  prompt, tools=tools or None,
                  timeout_s=binding.timeout_s, model=binding.model,
              )
          except Exception as e:
              logger.exception("analyst %s failed: %s", role.value, e)
              return {"role": role.value, "error": str(e), "raw_text": ""}

          structured = _try_parse_json(result.text)
          out = {
              "role": role.value,
              "provider": result.provider,
              "model": result.model,
              "tokens_in": result.tokens_in,
              "tokens_out": result.tokens_out,
              "latency_ms": result.latency_ms,
              "cli_command_hash": result.command_hash,
          }
          if structured is None:
              out["raw_text"] = result.text
          else:
              out["raw_text"] = result.text
              out.update(structured)
          return out

      return await asyncio.gather(*(_one(r) for r in analyst_roles))


  def _try_parse_json(text: str) -> dict[str, Any] | None:
      stripped = text.strip()
      # Try entire blob
      try:
          parsed = json.loads(stripped)
          if isinstance(parsed, dict):
              return parsed
      except json.JSONDecodeError:
          pass
      # Try ```json block
      if "```json" in stripped:
          start = stripped.find("```json") + len("```json")
          end = stripped.find("```", start)
          if end != -1:
              try:
                  parsed = json.loads(stripped[start:end].strip())
                  if isinstance(parsed, dict):
                      return parsed
              except json.JSONDecodeError:
                  pass
      return None
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_analyst_node.py -v
  ```
  Expected: 2 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/debate/analyst_node.py backend/tests/test_analyst_node.py
  git commit -m "feat(debate): add parallel analyst pool node"
  ```

---

## Task 8: Bull / Bear nodes

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/debate/bull_bear_nodes.py`
- Test: `backend/tests/test_bull_bear_nodes.py`

- [ ] **Step 1: Write failing test** — `backend/tests/test_bull_bear_nodes.py`:
  ```python
  """Tests for Bull and Bear debate nodes."""
  from __future__ import annotations

  import json
  from unittest.mock import AsyncMock, MagicMock

  import pytest

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.ports.llm_provider import LLMResult
  from daily_scheduler.infrastructure.adapters.debate.bull_bear_nodes import (
      run_bear,
      run_bull,
  )
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


  def _stub_result(text: str) -> LLMResult:
      return LLMResult(
          text=text, model="opus", provider="claude-code",
          tokens_in=0, tokens_out=0, latency_ms=10, command_hash="abc",
      )


  @pytest.mark.asyncio
  async def test_bull_returns_speech_with_structured() -> None:
      claude = MagicMock()
      claude.submit = AsyncMock(return_value=_stub_result(
          json.dumps({"direction": "BUY", "top_tickers": ["005930"], "risk_band": "MID"})
      ))
      codex = MagicMock()
      binding_repo = MagicMock(); binding_repo.get = MagicMock(return_value=None)
      router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

      speech = await run_bull(
          router=router,
          render_prompt=lambda role, ctx: "p",
          context={},
      )
      assert speech.agent_role is Role.BULL
      assert speech.structured_json["direction"] == "BUY"


  @pytest.mark.asyncio
  async def test_bear_returns_speech() -> None:
      claude = MagicMock()
      claude.submit = AsyncMock(return_value=_stub_result(
          json.dumps({"direction": "SELL", "top_tickers": ["000660"], "risk_band": "HIGH"})
      ))
      codex = MagicMock()
      binding_repo = MagicMock(); binding_repo.get = MagicMock(return_value=None)
      router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

      speech = await run_bear(
          router=router,
          render_prompt=lambda role, ctx: "p",
          context={},
      )
      assert speech.agent_role is Role.BEAR
      assert speech.structured_json["direction"] == "SELL"
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_bull_bear_nodes.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/debate/bull_bear_nodes.py`:
  ```python
  """Bull and Bear debate nodes."""
  from __future__ import annotations

  import json
  from collections.abc import Callable
  from typing import Any

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.entities.debate import Speech
  from daily_scheduler.infrastructure.adapters.council.role_registry import (
      tools_for_role,
  )
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


  async def run_bull(
      *,
      router: LLMRouter,
      render_prompt: Callable[[Role, dict[str, Any]], str],
      context: dict[str, Any],
  ) -> Speech:
      return await _run_debater(Role.BULL, router=router, render_prompt=render_prompt, context=context)


  async def run_bear(
      *,
      router: LLMRouter,
      render_prompt: Callable[[Role, dict[str, Any]], str],
      context: dict[str, Any],
  ) -> Speech:
      return await _run_debater(Role.BEAR, router=router, render_prompt=render_prompt, context=context)


  async def _run_debater(
      role: Role,
      *,
      router: LLMRouter,
      render_prompt: Callable[[Role, dict[str, Any]], str],
      context: dict[str, Any],
  ) -> Speech:
      provider, binding = router.resolve(role)
      prompt = render_prompt(role, context)
      result = await provider.submit(
          prompt, tools=tools_for_role(role) or None,
          timeout_s=binding.timeout_s, model=binding.model,
      )
      structured = _parse_or_empty(result.text)
      return Speech(
          agent_role=role,
          text=result.text,
          structured_json=structured,
          tokens_in=result.tokens_in,
          tokens_out=result.tokens_out,
          latency_ms=result.latency_ms,
          cli_command_hash=result.command_hash,
      )


  def _parse_or_empty(text: str) -> dict[str, Any]:
      stripped = text.strip()
      try:
          parsed = json.loads(stripped)
          if isinstance(parsed, dict):
              return parsed
      except json.JSONDecodeError:
          pass
      if "```json" in stripped:
          start = stripped.find("```json") + len("```json")
          end = stripped.find("```", start)
          if end != -1:
              try:
                  parsed = json.loads(stripped[start:end].strip())
                  if isinstance(parsed, dict):
                      return parsed
              except json.JSONDecodeError:
                  pass
      return {"raw_text": text}
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_bull_bear_nodes.py -v
  ```
  Expected: 2 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/debate/bull_bear_nodes.py backend/tests/test_bull_bear_nodes.py
  git commit -m "feat(debate): add Bull and Bear debate nodes"
  ```

---

## Task 9: Judge node — hybrid (rule + LLM + false-consensus)

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/debate/judge_node.py`
- Test: `backend/tests/test_judge_node.py`
- Create: `backend/tests/fixtures/judge_clear_consensus.json`
- Create: `backend/tests/fixtures/judge_clear_dissent.json`
- Create: `backend/tests/fixtures/judge_false_consensus.json`

- [ ] **Step 1: Write failing tests** — `backend/tests/test_judge_node.py`:
  ```python
  """Tests for the hybrid Judge node (rule + LLM)."""
  from __future__ import annotations

  import json
  from pathlib import Path
  from unittest.mock import AsyncMock, MagicMock

  import pytest

  from daily_scheduler.constants import JUDGE_LLM_THRESHOLD, JUDGE_RULE_THRESHOLD
  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.entities.debate import ConsensusScore, Speech
  from daily_scheduler.domain.ports.llm_provider import LLMResult
  from daily_scheduler.infrastructure.adapters.debate.judge_node import (
      _compute_rule_score,
      _detect_false_consensus_rule,
      run_judge,
  )
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


  FIXTURES = Path(__file__).parent / "fixtures"


  def _speech(role: Role, **structured) -> Speech:
      return Speech(
          agent_role=role, text="", structured_json=dict(structured),
          tokens_in=0, tokens_out=0, latency_ms=0, cli_command_hash="",
      )


  def test_rule_score_perfect_agreement() -> None:
      bull = _speech(Role.BULL, direction="BUY", top_tickers=["005930", "000660"], risk_band="MID")
      bear = _speech(Role.BEAR, direction="BUY", top_tickers=["005930", "000660"], risk_band="MID")
      s = _compute_rule_score(bull, bear, prior_rounds=[])
      assert s >= JUDGE_RULE_THRESHOLD


  def test_rule_score_opposite_direction() -> None:
      bull = _speech(Role.BULL, direction="BUY", top_tickers=["005930"], risk_band="LOW")
      bear = _speech(Role.BEAR, direction="SELL", top_tickers=["000660"], risk_band="HIGH")
      s = _compute_rule_score(bull, bear, prior_rounds=[])
      assert s < JUDGE_RULE_THRESHOLD


  def test_false_consensus_detected_when_one_side_collapses() -> None:
      """Round N-1: bear spoke 500 chars. Round N: bear speech 100 chars. Same direction now."""
      prev_bear = _speech(Role.BEAR, direction="SELL")
      prev_bear = Speech(
          agent_role=prev_bear.agent_role, text="x" * 500,
          structured_json=prev_bear.structured_json,
          tokens_in=0, tokens_out=0, latency_ms=0, cli_command_hash="",
      )
      prev_bull = _speech(Role.BULL, direction="BUY")
      from daily_scheduler.domain.entities.debate import Round
      prior = Round(
          index=0, bull_speech=prev_bull, bear_speech=prev_bear,
          judge_score=ConsensusScore(
              rule_score=0.3, llm_score=0.3, false_consensus=False,
              next_round_questions=[], dimensions={},
          ),
      )

      curr_bear = Speech(
          agent_role=Role.BEAR, text="x" * 50,  # >40% shorter
          structured_json={"direction": "BUY"},
          tokens_in=0, tokens_out=0, latency_ms=0, cli_command_hash="",
      )
      curr_bull = _speech(Role.BULL, direction="BUY")
      flag = _detect_false_consensus_rule(curr_bull, curr_bear, prior_rounds=[prior])
      assert flag is True


  @pytest.mark.asyncio
  async def test_run_judge_combines_rule_and_llm_consensus() -> None:
      bull = _speech(Role.BULL, direction="BUY", top_tickers=["005930"], risk_band="MID")
      bear = _speech(Role.BEAR, direction="BUY", top_tickers=["005930"], risk_band="MID")
      llm_envelope = {
          "agreement_score": 0.85,
          "dimensions": {"logical_coherence": 0.9, "evidence_quality": 0.85,
                          "remaining_disagreement": "", "sharpening_questions": []},
          "false_consensus_detected": False,
          "false_consensus_reason": None,
      }
      codex = MagicMock()
      codex.submit = AsyncMock(return_value=LLMResult(
          text=json.dumps(llm_envelope), model="gpt-5-codex", provider="codex",
          tokens_in=0, tokens_out=0, latency_ms=10, command_hash="abc",
      ))
      claude = MagicMock()
      binding_repo = MagicMock(); binding_repo.get = MagicMock(return_value=None)
      router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

      score = await run_judge(
          router=router,
          render_prompt=lambda role, ctx: "p",
          context={},
          bull=bull, bear=bear, prior_rounds=[],
      )
      assert isinstance(score, ConsensusScore)
      assert score.rule_score >= JUDGE_RULE_THRESHOLD
      assert score.llm_score == 0.85
      assert score.converged(rule_threshold=JUDGE_RULE_THRESHOLD, llm_threshold=JUDGE_LLM_THRESHOLD)


  @pytest.mark.asyncio
  async def test_run_judge_blocks_on_llm_false_consensus() -> None:
      bull = _speech(Role.BULL, direction="BUY", top_tickers=["005930"], risk_band="MID")
      bear = _speech(Role.BEAR, direction="BUY", top_tickers=["005930"], risk_band="MID")
      llm_envelope = {
          "agreement_score": 0.95,
          "dimensions": {"logical_coherence": 1.0, "evidence_quality": 0.9,
                          "remaining_disagreement": "",
                          "sharpening_questions": ["why did bear flip?"]},
          "false_consensus_detected": True,
          "false_consensus_reason": "bear collapsed to bull view without new evidence",
      }
      codex = MagicMock()
      codex.submit = AsyncMock(return_value=LLMResult(
          text=json.dumps(llm_envelope), model="gpt-5-codex", provider="codex",
          tokens_in=0, tokens_out=0, latency_ms=10, command_hash="abc",
      ))
      claude = MagicMock()
      binding_repo = MagicMock(); binding_repo.get = MagicMock(return_value=None)
      router = LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)

      score = await run_judge(
          router=router, render_prompt=lambda r, c: "p", context={},
          bull=bull, bear=bear, prior_rounds=[],
      )
      assert score.false_consensus is True
      assert score.converged(rule_threshold=JUDGE_RULE_THRESHOLD, llm_threshold=JUDGE_LLM_THRESHOLD) is False


  def test_judge_fixtures_exist() -> None:
      """Three fixture files anchor the judge regression scenarios."""
      assert (FIXTURES / "judge_clear_consensus.json").exists()
      assert (FIXTURES / "judge_clear_dissent.json").exists()
      assert (FIXTURES / "judge_false_consensus.json").exists()
  ```

- [ ] **Step 2:** Create the three fixture files.

  `backend/tests/fixtures/judge_clear_consensus.json`:
  ```json
  {
    "bull": {"direction": "BUY", "top_tickers": ["005930", "000660"], "risk_band": "MID"},
    "bear": {"direction": "BUY", "top_tickers": ["005930", "000660"], "risk_band": "MID"},
    "expected_converged": true
  }
  ```

  `backend/tests/fixtures/judge_clear_dissent.json`:
  ```json
  {
    "bull": {"direction": "BUY", "top_tickers": ["005930"], "risk_band": "LOW"},
    "bear": {"direction": "SELL", "top_tickers": ["000660"], "risk_band": "HIGH"},
    "expected_converged": false
  }
  ```

  `backend/tests/fixtures/judge_false_consensus.json`:
  ```json
  {
    "round_prior": {
      "bull": {"direction": "BUY", "top_tickers": ["005930"], "risk_band": "MID", "text_len": 500},
      "bear": {"direction": "SELL", "top_tickers": ["000660"], "risk_band": "HIGH", "text_len": 500}
    },
    "round_current": {
      "bull": {"direction": "BUY", "top_tickers": ["005930"], "risk_band": "MID", "text_len": 500},
      "bear": {"direction": "BUY", "top_tickers": ["005930"], "risk_band": "MID", "text_len": 80}
    },
    "expected_false_consensus_rule": true
  }
  ```

- [ ] **Step 3:** Run:
  ```bash
  cd backend && uv run pytest tests/test_judge_node.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 4:** Create `backend/src/daily_scheduler/infrastructure/adapters/debate/judge_node.py`:
  ```python
  """Hybrid Judge node — rule_score + llm_score + false-consensus detection."""
  from __future__ import annotations

  import json
  import logging
  from collections.abc import Callable
  from typing import Any

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.entities.debate import ConsensusScore, Round, Speech
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

  logger = logging.getLogger(__name__)


  async def run_judge(
      *,
      router: LLMRouter,
      render_prompt: Callable[[Role, dict[str, Any]], str],
      context: dict[str, Any],
      bull: Speech,
      bear: Speech,
      prior_rounds: list[Round],
  ) -> ConsensusScore:
      rule_score = _compute_rule_score(bull, bear, prior_rounds)
      fc_rule = _detect_false_consensus_rule(bull, bear, prior_rounds)

      provider, binding = router.resolve(Role.JUDGE)
      judge_context = dict(context)
      judge_context.update({
          "bull_text": bull.text,
          "bear_text": bear.text,
          "bull_struct": bull.structured_json,
          "bear_struct": bear.structured_json,
          "rule_score": rule_score,
          "prior_rounds_count": len(prior_rounds),
      })
      prompt = render_prompt(Role.JUDGE, judge_context)

      try:
          result = await provider.submit(
              prompt, tools=None, timeout_s=binding.timeout_s, model=binding.model,
          )
          envelope = _parse_judge_envelope(result.text)
      except Exception as e:
          logger.exception("judge LLM failed: %s", e)
          envelope = {
              "agreement_score": 0.0,
              "dimensions": {},
              "false_consensus_detected": False,
              "false_consensus_reason": f"judge LLM error: {e}",
          }

      llm_score = float(envelope.get("agreement_score", 0.0))
      fc_llm = bool(envelope.get("false_consensus_detected", False))
      questions = list(envelope.get("dimensions", {}).get("sharpening_questions", []) or [])

      return ConsensusScore(
          rule_score=rule_score,
          llm_score=llm_score,
          false_consensus=fc_rule or fc_llm,
          next_round_questions=questions,
          dimensions=dict(envelope.get("dimensions", {})),
      )


  def _compute_rule_score(
      bull: Speech,
      bear: Speech,
      prior_rounds: list[Round],
  ) -> float:
      b1 = bull.structured_json
      b2 = bear.structured_json

      direction = 1.0 if b1.get("direction") == b2.get("direction") else 0.0

      t1 = set(_as_list(b1.get("top_tickers", [])))
      t2 = set(_as_list(b2.get("top_tickers", [])))
      jaccard = (len(t1 & t2) / len(t1 | t2)) if (t1 | t2) else 0.0

      risk_diff = _risk_distance(b1.get("risk_band"), b2.get("risk_band"))
      risk_score = 1.0 - risk_diff  # 1.0 same, 0.0 max diff

      delta = _stability_vs_prev(bull, bear, prior_rounds)

      return 0.40 * direction + 0.30 * jaccard + 0.20 * risk_score + 0.10 * delta


  def _detect_false_consensus_rule(
      bull: Speech,
      bear: Speech,
      prior_rounds: list[Round],
  ) -> bool:
      if not prior_rounds:
          return False
      prev = prior_rounds[-1]
      prev_bear_len = len(prev.bear_speech.text)
      curr_bear_len = len(bear.text)
      prev_bull_len = len(prev.bull_speech.text)
      curr_bull_len = len(bull.text)

      bear_collapse = (prev_bear_len > 0 and curr_bear_len / prev_bear_len < 0.6)
      bull_collapse = (prev_bull_len > 0 and curr_bull_len / prev_bull_len < 0.6)
      direction_flipped = (
          prev.bull_speech.structured_json.get("direction")
          != prev.bear_speech.structured_json.get("direction")
          and bull.structured_json.get("direction")
          == bear.structured_json.get("direction")
      )
      return direction_flipped and (bear_collapse or bull_collapse)


  def _stability_vs_prev(
      bull: Speech, bear: Speech, prior_rounds: list[Round],
  ) -> float:
      if not prior_rounds:
          return 1.0
      prev = prior_rounds[-1]
      bull_same = (
          bull.structured_json.get("direction")
          == prev.bull_speech.structured_json.get("direction")
      )
      bear_same = (
          bear.structured_json.get("direction")
          == prev.bear_speech.structured_json.get("direction")
      )
      return 1.0 if (bull_same and bear_same) else 0.5


  def _risk_distance(a: object, b: object) -> float:
      ranks = {"LOW": 0, "MID": 1, "HIGH": 2}
      if a not in ranks or b not in ranks:
          return 0.5
      return abs(ranks[a] - ranks[b]) / 2.0


  def _as_list(value: Any) -> list[Any]:
      if isinstance(value, list):
          return value
      if isinstance(value, str):
          return [value]
      return []


  def _parse_judge_envelope(text: str) -> dict[str, Any]:
      stripped = text.strip()
      try:
          parsed = json.loads(stripped)
          if isinstance(parsed, dict):
              return parsed
      except json.JSONDecodeError:
          pass
      if "```json" in stripped:
          start = stripped.find("```json") + len("```json")
          end = stripped.find("```", start)
          if end != -1:
              try:
                  parsed = json.loads(stripped[start:end].strip())
                  if isinstance(parsed, dict):
                      return parsed
              except json.JSONDecodeError:
                  pass
      return {"agreement_score": 0.0, "dimensions": {}, "false_consensus_detected": False}
  ```

- [ ] **Step 5:** Run:
  ```bash
  cd backend && uv run pytest tests/test_judge_node.py -v
  ```
  Expected: 6 passed.

- [ ] **Step 6:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/debate/judge_node.py backend/tests/test_judge_node.py backend/tests/fixtures/
  git commit -m "feat(debate): add hybrid Judge node (rule + LLM + false-consensus)"
  ```

---

## Task 10: Decision nodes (Trader / Risk Mgmt / PM) and Editor/Publisher

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/debate/decision_nodes.py`
- Create: `backend/src/daily_scheduler/infrastructure/adapters/debate/editor_publisher_nodes.py`
- Test: `backend/tests/test_decision_nodes.py`
- Test: `backend/tests/test_editor_publisher_nodes.py`

- [ ] **Step 1: Write failing tests** — `backend/tests/test_decision_nodes.py`:
  ```python
  """Tests for Trader / RiskMgmt / PortfolioMgr nodes."""
  from __future__ import annotations

  import json
  from unittest.mock import AsyncMock, MagicMock

  import pytest

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.ports.llm_provider import LLMResult
  from daily_scheduler.infrastructure.adapters.debate.decision_nodes import (
      run_pm, run_risk_mgmt, run_trader,
  )
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


  def _r(text: str) -> LLMResult:
      return LLMResult(
          text=text, model="opus", provider="claude-code",
          tokens_in=0, tokens_out=0, latency_ms=10, command_hash="abc",
      )


  def _router(claude_text: str) -> LLMRouter:
      claude = MagicMock(); claude.submit = AsyncMock(return_value=_r(claude_text))
      codex = MagicMock()
      binding_repo = MagicMock(); binding_repo.get = MagicMock(return_value=None)
      return LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)


  @pytest.mark.asyncio
  async def test_trader_emits_speech_with_proposals() -> None:
      router = _router(json.dumps({"proposals": [{"ticker": "005930", "size_pct": 5}]}))
      s = await run_trader(router=router, render_prompt=lambda r, c: "p", context={})
      assert s.agent_role is Role.TRADER
      assert s.structured_json["proposals"][0]["ticker"] == "005930"


  @pytest.mark.asyncio
  async def test_risk_mgmt_returns_decision_speech() -> None:
      router = _router(json.dumps({"decision": "APPROVE", "modifications": []}))
      s = await run_risk_mgmt(router=router, render_prompt=lambda r, c: "p", context={})
      assert s.agent_role is Role.RISK_MGMT


  @pytest.mark.asyncio
  async def test_pm_emits_final_recommendations() -> None:
      payload = {
          "market_summary": "summary text",
          "recommendations": [{"ticker": "005930", "direction": "LONG", "timeframe": "DAY",
                               "entry_price": 70000, "target_price": 75000, "stop_loss": 68000}],
      }
      router = _router(json.dumps(payload))
      s = await run_pm(router=router, render_prompt=lambda r, c: "p", context={})
      assert s.agent_role is Role.PORTFOLIO_MGR
      assert s.structured_json["recommendations"][0]["ticker"] == "005930"
  ```

  And `backend/tests/test_editor_publisher_nodes.py`:
  ```python
  """Tests for Editor and Publisher nodes (news pipelines)."""
  from __future__ import annotations

  import json
  from unittest.mock import AsyncMock, MagicMock

  import pytest

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.ports.llm_provider import LLMResult
  from daily_scheduler.infrastructure.adapters.debate.editor_publisher_nodes import (
      run_editor, run_publisher,
  )
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


  def _router(text: str) -> LLMRouter:
      claude = MagicMock(); claude.submit = AsyncMock(return_value=LLMResult(
          text=text, model="opus", provider="claude-code",
          tokens_in=0, tokens_out=0, latency_ms=10, command_hash="abc",
      ))
      codex = MagicMock()
      binding_repo = MagicMock(); binding_repo.get = MagicMock(return_value=None)
      return LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)


  @pytest.mark.asyncio
  async def test_editor_returns_speech() -> None:
      payload = json.dumps({"news_items": [{"headline": "x", "summary": "y"}]})
      s = await run_editor(router=_router(payload), render_prompt=lambda r, c: "p", context={})
      assert s.agent_role is Role.EDITOR


  @pytest.mark.asyncio
  async def test_publisher_returns_speech() -> None:
      payload = json.dumps({"approve": True, "news_items": [{"headline": "x"}]})
      s = await run_publisher(router=_router(payload), render_prompt=lambda r, c: "p", context={})
      assert s.agent_role is Role.PUBLISHER
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_decision_nodes.py tests/test_editor_publisher_nodes.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/debate/decision_nodes.py`:
  ```python
  """Trader, RiskMgmt, PortfolioMgr — sequential decision nodes."""
  from __future__ import annotations

  from collections.abc import Callable
  from typing import Any

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.entities.debate import Speech
  from daily_scheduler.infrastructure.adapters.debate.bull_bear_nodes import _parse_or_empty
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


  async def run_trader(*, router: LLMRouter, render_prompt, context) -> Speech:
      return await _run(Role.TRADER, router, render_prompt, context)


  async def run_risk_mgmt(*, router: LLMRouter, render_prompt, context) -> Speech:
      return await _run(Role.RISK_MGMT, router, render_prompt, context)


  async def run_pm(*, router: LLMRouter, render_prompt, context) -> Speech:
      return await _run(Role.PORTFOLIO_MGR, router, render_prompt, context)


  async def _run(
      role: Role,
      router: LLMRouter,
      render_prompt: Callable[[Role, dict[str, Any]], str],
      context: dict[str, Any],
  ) -> Speech:
      provider, binding = router.resolve(role)
      prompt = render_prompt(role, context)
      result = await provider.submit(
          prompt, tools=None, timeout_s=binding.timeout_s, model=binding.model,
      )
      structured = _parse_or_empty(result.text)
      return Speech(
          agent_role=role, text=result.text, structured_json=structured,
          tokens_in=result.tokens_in, tokens_out=result.tokens_out,
          latency_ms=result.latency_ms, cli_command_hash=result.command_hash,
      )
  ```

  Create `backend/src/daily_scheduler/infrastructure/adapters/debate/editor_publisher_nodes.py`:
  ```python
  """Editor and Publisher — sequential nodes for news pipelines."""
  from __future__ import annotations

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.entities.debate import Speech
  from daily_scheduler.infrastructure.adapters.debate.bull_bear_nodes import _parse_or_empty
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter
  from daily_scheduler.infrastructure.adapters.council.role_registry import tools_for_role


  async def run_editor(*, router: LLMRouter, render_prompt, context) -> Speech:
      return await _run(Role.EDITOR, router, render_prompt, context)


  async def run_publisher(*, router: LLMRouter, render_prompt, context) -> Speech:
      return await _run(Role.PUBLISHER, router, render_prompt, context)


  async def _run(role, router, render_prompt, context):
      provider, binding = router.resolve(role)
      prompt = render_prompt(role, context)
      result = await provider.submit(
          prompt, tools=tools_for_role(role) or None,
          timeout_s=binding.timeout_s, model=binding.model,
      )
      return Speech(
          agent_role=role, text=result.text, structured_json=_parse_or_empty(result.text),
          tokens_in=result.tokens_in, tokens_out=result.tokens_out,
          latency_ms=result.latency_ms, cli_command_hash=result.command_hash,
      )
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_decision_nodes.py tests/test_editor_publisher_nodes.py -v
  ```
  Expected: 5 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/debate/decision_nodes.py backend/src/daily_scheduler/infrastructure/adapters/debate/editor_publisher_nodes.py backend/tests/test_decision_nodes.py backend/tests/test_editor_publisher_nodes.py
  git commit -m "feat(debate): add Trader/RiskMgmt/PM + Editor/Publisher nodes"
  ```

---

## Task 11: Prompt templates loader

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/council/prompt_templates.py`
- Create: `backend/src/daily_scheduler/templates/prompts/agents/*.j2` (15 files)
- Test: `backend/tests/test_prompt_templates.py`

- [ ] **Step 1: Write failing test** — `backend/tests/test_prompt_templates.py`:
  ```python
  """Tests for agent prompt template loader."""
  from __future__ import annotations

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.infrastructure.adapters.council.prompt_templates import (
      render_agent_prompt,
  )


  def test_loader_renders_for_each_role() -> None:
      ctx = {
          "pipeline": "daily", "date": "2026-05-25",
          "market_data": "KOSPI flat", "screening": "no candidates",
          "retrospective": "win rate 60%", "memory_context": [],
          "analyst_reports": [], "prior_rounds": [], "consensus_score": None,
      }
      for role in Role:
          out = render_agent_prompt(role, ctx)
          assert isinstance(out, str)
          assert len(out) > 0
  ```

- [ ] **Step 2:** Run test:
  ```bash
  cd backend && uv run pytest tests/test_prompt_templates.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/council/prompt_templates.py`:
  ```python
  """Render agent system prompts from Jinja2 templates."""
  from __future__ import annotations

  from pathlib import Path
  from typing import Any

  from jinja2 import Environment, FileSystemLoader

  from daily_scheduler.domain.entities.agent import Role

  _TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "prompts" / "agents"

  _env = Environment(
      loader=FileSystemLoader(str(_TEMPLATES_DIR)),
      trim_blocks=True, lstrip_blocks=True,
      autoescape=False,
  )


  def render_agent_prompt(role: Role, context: dict[str, Any]) -> str:
      template_name = f"{role.value}.j2"
      tpl = _env.get_template(template_name)
      return tpl.render(**context)
  ```

- [ ] **Step 4:** Create the 15 template files under `backend/src/daily_scheduler/templates/prompts/agents/`. Each is a minimal Jinja2 template that produces a usable prompt. Use this content for **kr_fundamentals.j2** (similar pattern for other analyst roles):

  ```jinja2
  You are the KR Fundamentals Analyst on the daily-scheduler investment council.
  Your job: produce a structured fundamentals report on Korean equities for {{ date }}.

  ## Market Data
  {{ market_data }}

  ## Screening Universe
  {{ screening }}

  ## Retrospective Context
  {{ retrospective }}

  ## Memory Context (prior decisions and lessons)
  {% for m in memory_context %}
  - [{{ m.date }}] {{ m.summary }}{% if m.outcome %} (outcome: {{ m.outcome }}){% endif %}
  {% else %}
  (no relevant prior memory)
  {% endfor %}

  ## Task
  Use WebSearch and WebFetch to fetch:
  - Q4/recent earnings on KOSPI top holdings
  - Korean macro indicators (KOSPI, KRW/USD, BoK rate, CPI)

  Respond ONLY with a JSON object:
  ```json
  {
    "role": "kr_fundamentals",
    "top_picks": ["005930", ...],
    "rationale": "...",
    "key_metrics": {"005930": {"per": 12.3, "roe": 8.1}},
    "risks": ["...", "..."]
  }
  ```
  ```

  Use the same skeleton for **us_fundamentals.j2**, **kr_technical.j2**, **us_technical.j2**, **news_sentiment.j2** — adjust the role label, the data sources to fetch, and the expected JSON keys (e.g. technical → rsi/macd; news_sentiment → headlines).

  For **bull.j2** / **bear.j2**:
  ```jinja2
  You are the {{ role.value | upper }} Researcher debating against the {{ "BEAR" if role.value == "bull" else "BULL" }}.

  ## Analyst Reports
  {% for r in analyst_reports %}
  - **{{ r.role }}**: {{ r.get('rationale', r.get('raw_text', ''))[:500] }}
  {% endfor %}

  ## Prior Rounds (this debate so far)
  {% for rnd in prior_rounds %}
  ### Round {{ rnd.index + 1 }}
  Bull: {{ rnd.bull_speech.text[:400] }}
  Bear: {{ rnd.bear_speech.text[:400] }}
  Judge: rule={{ "%.2f" | format(rnd.judge_score.rule_score) }}, llm={{ "%.2f" | format(rnd.judge_score.llm_score) }}, converged={{ rnd.judge_score.converged(rule_threshold=0.75, llm_threshold=0.70) }}
  {% endfor %}

  ## Task
  Make the strongest case from your side. Respond with JSON:
  ```json
  {
    "direction": "BUY" | "HOLD" | "SELL",
    "top_tickers": ["...", "..."],
    "risk_band": "LOW" | "MID" | "HIGH",
    "argument": "...",
    "evidence": ["...", "..."]
  }
  ```
  ```

  For **judge.j2**:
  ```jinja2
  You are the Judge evaluating consensus between Bull and Bear.

  Current rule_score (precomputed): {{ "%.3f" | format(rule_score) }}

  ## Bull's latest position
  {{ bull_text }}

  Structured: {{ bull_struct | tojson }}

  ## Bear's latest position
  {{ bear_text }}

  Structured: {{ bear_struct | tojson }}

  Prior rounds: {{ prior_rounds_count }}

  ## Task — evaluate qualitative consensus
  Detect false consensus signals:
  - Did either side collapse without new evidence?
  - Did either side adopt the other's terminology without addressing substance?

  Respond ONLY with JSON:
  ```json
  {
    "agreement_score": 0.0,
    "dimensions": {
      "logical_coherence": 0.0,
      "evidence_quality": 0.0,
      "remaining_disagreement": "...",
      "sharpening_questions": ["..."]
    },
    "false_consensus_detected": false,
    "false_consensus_reason": null
  }
  ```
  ```

  For **trader.j2**, **risk_mgmt.j2**, **portfolio_mgr.j2** — sequential decision templates. Use a single template structure with a header describing the role and a JSON output schema. For the **portfolio_mgr.j2** specifically, the JSON output is the largest because it produces the entire `ReportContent`-compatible payload:

  ```jinja2
  You are the Portfolio Manager — produce the final daily report.

  Synthesize:
  - Analyst reports: {{ analyst_reports | tojson }}
  - Final debate consensus (rule={{ "%.2f" | format(consensus_score.rule_score) }}, llm={{ "%.2f" | format(consensus_score.llm_score) }}, converged={{ consensus_score.converged(rule_threshold=0.75, llm_threshold=0.70) }})
  - Bull last: {{ prior_rounds[-1].bull_speech.text[:400] if prior_rounds else "" }}
  - Bear last: {{ prior_rounds[-1].bear_speech.text[:400] if prior_rounds else "" }}
  - Market data: {{ market_data }}
  - Screening: {{ screening }}
  - Retrospective: {{ retrospective }}

  Respond with a single JSON object matching the daily report schema:
  ```json
  {
    "report_date": "{{ date }}",
    "market_summary": "...",
    "alert_banner": "",
    "news_items": [...],
    "causal_chains": [...],
    "risk_matrix": [...],
    "sector_analysis": [...],
    "sentiment": [...],
    "technicals": [...],
    "recommendations": [
      {"ticker": "...", "name": "...", "market": "KOSPI", "direction": "LONG",
       "timeframe": "DAY", "entry_price": 0, "target_price": 0, "stop_loss": 0,
       "sector": "...", "rationale": "...", "causal_chain_summary": "...",
       "risk_reward_ratio": 1.5, "confidence": "medium"}
    ],
    "upcoming_events": [...],
    "past_performance_commentary": "...",
    "disclaimer": "Investment risk warning..."
  }
  ```
  ```

  For **editor.j2** / **publisher.j2** (news pipelines), produce JSON keys `news_items[]` matching ReportContent's news_items schema.

  For **perf_analyst.j2** / **lessons_researcher.j2** (weekly), produce JSON suitable for the weekly report (e.g. `weekly_stats`, `lessons[]`).

  Each template can be ~30–50 lines. Keep schemas explicit so the LLM produces parseable output.

- [ ] **Step 5:** Run:
  ```bash
  cd backend && uv run pytest tests/test_prompt_templates.py -v
  ```
  Expected: 1 passed.

- [ ] **Step 6:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/council/prompt_templates.py backend/src/daily_scheduler/templates/prompts/agents/ backend/tests/test_prompt_templates.py
  git commit -m "feat(council): add agent prompt templates for all 15 roles"
  ```

---

## Task 12: Memory auto-injection helper

**Files:**
- Create: `backend/src/daily_scheduler/application/use_cases/memory_injection.py`
- Test: `backend/tests/test_memory_injection.py`

- [ ] **Step 1: Write failing test** — `backend/tests/test_memory_injection.py`:
  ```python
  """Tests for memory auto-injection."""
  from __future__ import annotations

  from datetime import date

  from daily_scheduler.application.use_cases.memory_injection import (
      build_memory_context,
  )
  from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode
  from daily_scheduler.domain.ports.memory_store import MemoryQuery


  class _FakeStore:
      def __init__(self, nodes):
          self._nodes = nodes

      def query_metadata(self, q: MemoryQuery):
          return [n for n in self._nodes if q.symbol in (None, n.symbol)]

      def query_keyword(self, text, limit=10):
          return [n for n in self._nodes if text in n.summary][:limit]

      def traverse_tree(self, query, max_depth=3):
          return self._nodes[:5]


  def _node(i):
      return MemoryNode(
          id=f"id{i}", kind=MemoryKind.DECISION, date=date(2026, 5, 24),
          summary=f"summary {i}", body="body",
          symbol=f"SYM{i}", sector="x", strategy="DAY",
          outcome=None, debate_id=None,
      )


  def test_build_memory_context_returns_top_k() -> None:
      store = _FakeStore([_node(i) for i in range(10)])
      out = build_memory_context(
          store=store,
          tickers=["SYM0", "SYM1"],
          pipeline="daily",
          regime="neutral",
          top_k=5,
      )
      assert len(out) <= 5
      assert all(isinstance(n, MemoryNode) for n in out)


  def test_build_memory_context_empty_store_returns_empty() -> None:
      store = _FakeStore([])
      out = build_memory_context(
          store=store, tickers=[], pipeline="daily",
          regime="neutral", top_k=5,
      )
      assert out == []


  def test_dedup_preserves_order() -> None:
      n = _node(0)
      class Store(_FakeStore):
          def query_metadata(self, q):
              return [n, n]
          def traverse_tree(self, query, max_depth=3):
              return [n]
      store = Store([])
      out = build_memory_context(
          store=store, tickers=["SYM0"], pipeline="daily",
          regime="x", top_k=5,
      )
      assert len(out) == 1
  ```

- [ ] **Step 2:** Run test:
  ```bash
  cd backend && uv run pytest tests/test_memory_injection.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/application/use_cases/memory_injection.py`:
  ```python
  """Memory auto-injection — picks top-K relevant MemoryNodes for a debate."""
  from __future__ import annotations

  from daily_scheduler.constants import MEMORY_AUTO_INJECT_TOP_K
  from daily_scheduler.domain.entities.memory_node import MemoryNode
  from daily_scheduler.domain.ports.memory_store import MemoryQuery, MemoryStorePort


  def build_memory_context(
      *,
      store: MemoryStorePort,
      tickers: list[str],
      pipeline: str,
      regime: str,
      top_k: int = MEMORY_AUTO_INJECT_TOP_K,
  ) -> list[MemoryNode]:
      """Return up to top_k memory nodes likely relevant to this debate."""
      by_meta: list[MemoryNode] = []
      for t in tickers[:10]:
          by_meta.extend(store.query_metadata(MemoryQuery(symbol=t, limit=2)))

      by_tree = store.traverse_tree(query=f"{regime} {pipeline}", max_depth=3)

      seen: set[str] = set()
      out: list[MemoryNode] = []
      for n in by_meta + by_tree:
          if n.id in seen:
              continue
          seen.add(n.id)
          out.append(n)
          if len(out) >= top_k:
              break
      return out
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_memory_injection.py -v
  ```
  Expected: 3 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/application/use_cases/memory_injection.py backend/tests/test_memory_injection.py
  git commit -m "feat(application): add memory auto-injection helper"
  ```

---

## Task 13: Graph builder + debate orchestrator

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/debate/graph_builder.py`
- Create: `backend/src/daily_scheduler/application/use_cases/debate_engine.py`
- Test: `backend/tests/test_graph_builder.py`

The graph builder produces a LangGraph `StateGraph` configured for each pipeline. The orchestrator runs the graph and returns a `DebateGraph` aggregate.

- [ ] **Step 1: Write failing test** — `backend/tests/test_graph_builder.py`:
  ```python
  """Smoke tests for graph builder + orchestrator (with stub nodes)."""
  from __future__ import annotations

  import json
  from datetime import date
  from unittest.mock import AsyncMock, MagicMock

  import pytest

  from daily_scheduler.application.use_cases.debate_engine import run_debate
  from daily_scheduler.domain.entities.debate import DebateState
  from daily_scheduler.domain.ports.llm_provider import LLMResult
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


  def _r(text: str) -> LLMResult:
      return LLMResult(
          text=text, model="opus", provider="claude-code",
          tokens_in=0, tokens_out=0, latency_ms=1, command_hash="abc",
      )


  def _mock_router_for_convergence() -> LLMRouter:
      """All agents agree perfectly → converge in round 1."""
      claude = MagicMock()
      converging_response = {
          "direction": "BUY", "top_tickers": ["005930"], "risk_band": "MID",
          "argument": "good", "evidence": ["e1"],
          "proposals": [{"ticker": "005930"}],
          "decision": "APPROVE",
          "report_date": "2026-05-25", "market_summary": "x",
          "alert_banner": "", "news_items": [], "causal_chains": [], "risk_matrix": [],
          "sector_analysis": [], "sentiment": [], "technicals": [],
          "recommendations": [{
              "ticker": "005930", "name": "Samsung", "market": "KOSPI",
              "direction": "LONG", "timeframe": "DAY",
              "entry_price": 70000, "target_price": 75000, "stop_loss": 68000,
              "sector": "semi", "rationale": "good",
              "causal_chain_summary": "x", "risk_reward_ratio": 2.5, "confidence": "high",
          }],
          "upcoming_events": [], "past_performance_commentary": "", "disclaimer": "x",
      }
      claude.submit = AsyncMock(return_value=_r(json.dumps(converging_response)))
      codex = MagicMock()
      codex.submit = AsyncMock(return_value=_r(json.dumps({
          "agreement_score": 0.95,
          "dimensions": {"logical_coherence": 1.0, "evidence_quality": 0.9,
                          "remaining_disagreement": "", "sharpening_questions": []},
          "false_consensus_detected": False, "false_consensus_reason": None,
      })))
      binding_repo = MagicMock(); binding_repo.get = MagicMock(return_value=None)
      return LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)


  @pytest.mark.asyncio
  async def test_daily_debate_runs_and_converges() -> None:
      router = _mock_router_for_convergence()
      graph = await run_debate(
          pipeline="daily",
          router=router,
          memory_store=MagicMock(query_metadata=MagicMock(return_value=[]),
                                  traverse_tree=MagicMock(return_value=[])),
          context={
              "date": date(2026, 5, 25).isoformat(),
              "market_data": "KOSPI flat", "screening": "n/a",
              "retrospective": "x",
              "tickers": ["005930"], "regime": "neutral",
          },
          triggered_by="manual",
          max_rounds=3,
      )
      assert graph.state in (DebateState.CONVERGED, DebateState.MAX_ROUNDS_DISSENT)
      assert graph.verdict is not None
      assert graph.verdict.report_content_json["recommendations"][0]["ticker"] == "005930"


  @pytest.mark.asyncio
  async def test_news_pipeline_runs_without_trader_or_pm() -> None:
      router = _mock_router_for_convergence()
      graph = await run_debate(
          pipeline="news", router=router,
          memory_store=MagicMock(query_metadata=MagicMock(return_value=[]),
                                  traverse_tree=MagicMock(return_value=[])),
          context={"date": "2026-05-25", "market_data": "", "screening": "",
                   "retrospective": "", "tickers": [], "regime": "neutral"},
          triggered_by="scheduler", max_rounds=2,
      )
      assert graph.pipeline == "news"
      assert graph.verdict is not None
      # News pipeline produces news_items, not recommendations
      assert "news_items" in graph.verdict.report_content_json
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_graph_builder.py -v
  ```
  Expected: ImportError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/debate/graph_builder.py`:
  ```python
  """LangGraph state-graph builders for each pipeline.

  Note: Plan 2 implements the debate flow in a hand-written async orchestrator
  (`debate_engine.py`) for simplicity and testability. The "graph builder" name
  is retained for forward compatibility — a future iteration can swap to
  LangGraph's StateGraph if we need built-in checkpoint replay. For now,
  LangGraph's SqliteSaver is wired into the orchestrator for state checkpoints.
  """
  from __future__ import annotations

  from typing import Literal

  Pipeline = Literal["daily", "news", "global-news", "weekly"]


  def is_news_pipeline(pipeline: str) -> bool:
      return pipeline in ("news", "global-news")


  def is_weekly_pipeline(pipeline: str) -> bool:
      return pipeline == "weekly"
  ```

  Create `backend/src/daily_scheduler/application/use_cases/debate_engine.py`:
  ```python
  """Debate orchestrator — runs the agent graph for a single pipeline invocation."""
  from __future__ import annotations

  import logging
  from datetime import datetime
  from typing import Any

  from ulid import ULID

  from daily_scheduler.constants import (
      JUDGE_LLM_THRESHOLD, JUDGE_RULE_THRESHOLD,
      MAX_DEBATE_ROUNDS_DAILY, MAX_DEBATE_ROUNDS_NEWS, MAX_DEBATE_ROUNDS_WEEKLY,
  )
  from daily_scheduler.domain.entities.agent import Role, roles_for_pipeline
  from daily_scheduler.domain.entities.debate import (
      ConsensusScore, DebateGraph, DebateState, Round, Speech, Verdict,
  )
  from daily_scheduler.domain.ports.memory_store import MemoryStorePort
  from daily_scheduler.infrastructure.adapters.council.prompt_templates import (
      render_agent_prompt,
  )
  from daily_scheduler.infrastructure.adapters.debate.analyst_node import run_analyst_pool
  from daily_scheduler.infrastructure.adapters.debate.bull_bear_nodes import (
      run_bear, run_bull,
  )
  from daily_scheduler.infrastructure.adapters.debate.decision_nodes import (
      run_pm, run_risk_mgmt, run_trader,
  )
  from daily_scheduler.infrastructure.adapters.debate.editor_publisher_nodes import (
      run_editor, run_publisher,
  )
  from daily_scheduler.infrastructure.adapters.debate.graph_builder import (
      is_news_pipeline, is_weekly_pipeline,
  )
  from daily_scheduler.infrastructure.adapters.debate.judge_node import run_judge
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter

  logger = logging.getLogger(__name__)


  async def run_debate(
      *,
      pipeline: str,
      router: LLMRouter,
      memory_store: MemoryStorePort,
      context: dict[str, Any],
      triggered_by: str,
      max_rounds: int | None = None,
  ) -> DebateGraph:
      """Run a complete debate for a pipeline. Returns the aggregate DebateGraph."""
      debate_id = str(ULID())
      started = datetime.now()
      if max_rounds is None:
          max_rounds = _default_max_rounds(pipeline)

      analyst_reports: list[dict[str, Any]] = []
      rounds: list[Round] = []
      verdict: Verdict | None = None
      state = DebateState.RUNNING
      error: str | None = None

      try:
          # Memory context (precomputed once at start)
          memory_context = []
          try:
              from daily_scheduler.application.use_cases.memory_injection import (
                  build_memory_context,
              )
              memory_context = build_memory_context(
                  store=memory_store,
                  tickers=list(context.get("tickers", [])),
                  pipeline=pipeline,
                  regime=str(context.get("regime", "neutral")),
              )
          except Exception as e:  # memory failure must not fail debate
              logger.warning("memory_injection failed (continuing): %s", e)

          base_ctx = dict(context)
          base_ctx["memory_context"] = memory_context

          # 1. Analyst pool (parallel)
          analyst_roles = [r for r in roles_for_pipeline(pipeline) if _is_analyst(r)]
          if analyst_roles:
              analyst_reports = await run_analyst_pool(
                  analyst_roles=analyst_roles, router=router,
                  render_prompt=render_agent_prompt,
                  context=base_ctx,
              )
              base_ctx["analyst_reports"] = analyst_reports

          # 2. Debate loop (Bull/Bear/Judge or Editor/Publisher/Judge)
          if is_weekly_pipeline(pipeline):
              # Weekly: sequential PERF_ANALYST → LESSONS_RESEARCHER → PM
              # No analyst pool, no debate loop.
              perf = await _run_single(Role.PERF_ANALYST, router, base_ctx)
              base_ctx["perf"] = perf.structured_json
              lessons = await _run_single(Role.LESSONS_RESEARCHER, router, base_ctx)
              base_ctx["lessons"] = lessons.structured_json
              base_ctx["prior_rounds"] = []
              base_ctx["consensus_score"] = None
              pm_speech = await run_pm(
                  router=router, render_prompt=render_agent_prompt, context=base_ctx,
              )
              verdict = _build_verdict(debate_id, DebateState.CONVERGED, pm_speech, [])
              state = DebateState.CONVERGED
          elif is_news_pipeline(pipeline):
              for idx in range(max_rounds):
                  base_ctx["prior_rounds"] = rounds
                  ed = await run_editor(
                      router=router, render_prompt=render_agent_prompt, context=base_ctx,
                  )
                  pub_ctx = dict(base_ctx); pub_ctx["editor"] = ed.structured_json
                  pub = await run_publisher(
                      router=router, render_prompt=render_agent_prompt, context=pub_ctx,
                  )
                  score = await run_judge(
                      router=router, render_prompt=render_agent_prompt, context=base_ctx,
                      bull=ed, bear=pub, prior_rounds=rounds,
                  )
                  rnd = Round(index=idx, bull_speech=ed, bear_speech=pub, judge_score=score)
                  rounds.append(rnd)
                  if score.converged(
                      rule_threshold=JUDGE_RULE_THRESHOLD, llm_threshold=JUDGE_LLM_THRESHOLD,
                  ):
                      state = DebateState.CONVERGED
                      break
              else:
                  state = DebateState.MAX_ROUNDS_DISSENT
              # Publisher's final speech is the verdict payload for news
              final = rounds[-1].bear_speech if rounds else None
              if final:
                  verdict = _build_verdict(debate_id, state, final, [])
          else:
              # Daily pipeline: full debate
              for idx in range(max_rounds):
                  base_ctx["prior_rounds"] = rounds
                  bull = await run_bull(
                      router=router, render_prompt=render_agent_prompt, context=base_ctx,
                  )
                  bear_ctx = dict(base_ctx); bear_ctx["bull"] = bull.structured_json
                  bear = await run_bear(
                      router=router, render_prompt=render_agent_prompt, context=bear_ctx,
                  )
                  score = await run_judge(
                      router=router, render_prompt=render_agent_prompt, context=base_ctx,
                      bull=bull, bear=bear, prior_rounds=rounds,
                  )
                  rnd = Round(index=idx, bull_speech=bull, bear_speech=bear, judge_score=score)
                  rounds.append(rnd)
                  if score.converged(
                      rule_threshold=JUDGE_RULE_THRESHOLD, llm_threshold=JUDGE_LLM_THRESHOLD,
                  ):
                      state = DebateState.CONVERGED
                      break
              else:
                  state = DebateState.MAX_ROUNDS_DISSENT

              # Trader → Risk Mgmt → PM
              base_ctx["prior_rounds"] = rounds
              base_ctx["consensus_score"] = (
                  rounds[-1].judge_score if rounds else ConsensusScore(
                      rule_score=0.0, llm_score=0.0,
                      false_consensus=False, next_round_questions=[], dimensions={},
                  )
              )
              _trader = await run_trader(
                  router=router, render_prompt=render_agent_prompt, context=base_ctx,
              )
              base_ctx["trader"] = _trader.structured_json
              _risk = await run_risk_mgmt(
                  router=router, render_prompt=render_agent_prompt, context=base_ctx,
              )
              base_ctx["risk"] = _risk.structured_json
              pm_speech = await run_pm(
                  router=router, render_prompt=render_agent_prompt, context=base_ctx,
              )
              verdict = _build_verdict(debate_id, state, pm_speech, [])

      except Exception as e:
          logger.exception("debate failed: %s", e)
          state = DebateState.FAILED
          error = str(e)

      return DebateGraph(
          id=debate_id, pipeline=pipeline, state=state,
          rounds=rounds, analyst_reports=analyst_reports, verdict=verdict,
          started_at=started, ended_at=datetime.now(),
          triggered_by=triggered_by, error=error,
      )


  def _is_analyst(role: Role) -> bool:
      return role in (
          Role.KR_FUNDAMENTALS, Role.US_FUNDAMENTALS,
          Role.KR_TECHNICAL, Role.US_TECHNICAL, Role.NEWS_SENT,
      )


  def _default_max_rounds(pipeline: str) -> int:
      if pipeline == "daily":
          return MAX_DEBATE_ROUNDS_DAILY
      if pipeline in ("news", "global-news"):
          return MAX_DEBATE_ROUNDS_NEWS
      return max(MAX_DEBATE_ROUNDS_WEEKLY, 1)


  def _build_verdict(
      debate_id: str,
      state: DebateState,
      pm_speech: Speech,
      recommendation_dicts: list[dict[str, Any]],
  ) -> Verdict:
      payload = dict(pm_speech.structured_json)
      recs = payload.get("recommendations", []) or recommendation_dicts
      return Verdict(
          debate_id=debate_id,
          consensus=state,
          report_content_json=payload,
          recommendation_dicts=recs if isinstance(recs, list) else [],
      )


  async def _run_single(role: Role, router: LLMRouter, ctx: dict[str, Any]) -> Speech:
      """One-shot agent invocation (used by weekly sequential flow)."""
      from daily_scheduler.infrastructure.adapters.debate.bull_bear_nodes import (
          _parse_or_empty,
      )

      provider, binding = router.resolve(role)
      prompt = render_agent_prompt(role, ctx)
      result = await provider.submit(
          prompt, tools=None, timeout_s=binding.timeout_s, model=binding.model,
      )
      return Speech(
          agent_role=role, text=result.text,
          structured_json=_parse_or_empty(result.text),
          tokens_in=result.tokens_in, tokens_out=result.tokens_out,
          latency_ms=result.latency_ms, cli_command_hash=result.command_hash,
      )
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_graph_builder.py -v
  ```
  Expected: 2 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/debate/graph_builder.py backend/src/daily_scheduler/application/use_cases/debate_engine.py backend/tests/test_graph_builder.py
  git commit -m "feat(debate): add graph builder + async debate orchestrator"
  ```

---

## Task 14: Verdict serializer (ReportContent compatibility)

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/council/verdict_serializer.py`
- Test: `backend/tests/test_verdict_serializer.py`

- [ ] **Step 1: Write failing test** — `backend/tests/test_verdict_serializer.py`:
  ```python
  """Tests that Verdict serializes to a JSON parseable by parse_report_content."""
  from __future__ import annotations

  import json

  from daily_scheduler.domain.entities.debate import DebateState, Verdict
  from daily_scheduler.infrastructure.adapters.claude.parser import parse_report_content
  from daily_scheduler.infrastructure.adapters.council.verdict_serializer import (
      verdict_to_report_json,
  )


  def test_verdict_round_trips_through_existing_parser() -> None:
      payload = {
          "report_date": "2026-05-25",
          "market_summary": "summary",
          "alert_banner": "",
          "news_items": [
              {"category": "policy", "headline": "h", "source": "s",
               "published_at": "2026-05-25", "summary": "x",
               "impact_level": "high", "affected_sectors": ["semi"]}
          ],
          "causal_chains": [],
          "risk_matrix": [],
          "sector_analysis": [],
          "sentiment": [],
          "technicals": [],
          "recommendations": [
              {"ticker": "005930", "name": "Samsung", "market": "KOSPI",
               "direction": "LONG", "timeframe": "DAY",
               "entry_price": 70000, "target_price": 75000, "stop_loss": 68000,
               "sector": "semi", "rationale": "x", "causal_chain_summary": "y",
               "risk_reward_ratio": 2.5, "confidence": "high"}
          ],
          "upcoming_events": [],
          "past_performance_commentary": "",
          "disclaimer": "x",
      }
      verdict = Verdict(
          debate_id="d1", consensus=DebateState.CONVERGED,
          report_content_json=payload,
          recommendation_dicts=payload["recommendations"],
      )
      raw = verdict_to_report_json(verdict)
      assert isinstance(raw, str)
      parsed = parse_report_content(raw)
      assert parsed is not None
      assert parsed.report_date == "2026-05-25"
      assert len(parsed.recommendations) == 1


  def test_verdict_to_report_json_emits_compact_or_indented_json() -> None:
      v = Verdict(
          debate_id="d2", consensus=DebateState.CONVERGED,
          report_content_json={"report_date": "2026-05-25"},
          recommendation_dicts=[],
      )
      out = verdict_to_report_json(v)
      assert json.loads(out)["report_date"] == "2026-05-25"
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_verdict_serializer.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/council/verdict_serializer.py`:
  ```python
  """Serializes a Verdict to the JSON shape consumed by the legacy parser.

  The output of verdict_to_report_json must round-trip through
  daily_scheduler.infrastructure.adapters.claude.parser.parse_report_content
  to keep all existing RPT-* acceptance tests passing.
  """
  from __future__ import annotations

  import json

  from daily_scheduler.domain.entities.debate import Verdict


  def verdict_to_report_json(verdict: Verdict) -> str:
      """Emit a JSON string matching parse_report_content's expected shape."""
      payload = dict(verdict.report_content_json)
      # Ensure required keys are present (the parser tolerates absence, but
      # downstream renderers may expect them)
      payload.setdefault("report_date", "")
      payload.setdefault("market_summary", "")
      payload.setdefault("alert_banner", "")
      payload.setdefault("news_items", [])
      payload.setdefault("causal_chains", [])
      payload.setdefault("risk_matrix", [])
      payload.setdefault("sector_analysis", [])
      payload.setdefault("sentiment", [])
      payload.setdefault("technicals", [])
      payload.setdefault("recommendations", verdict.recommendation_dicts or [])
      payload.setdefault("upcoming_events", [])
      payload.setdefault("past_performance_commentary", "")
      payload.setdefault("disclaimer", "")
      return json.dumps(payload, ensure_ascii=False)
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_verdict_serializer.py -v
  ```
  Expected: 2 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/council/verdict_serializer.py backend/tests/test_verdict_serializer.py
  git commit -m "feat(council): add Verdict → ReportContent-compatible JSON serializer"
  ```

---

## Task 15: CouncilNewsProvider (implements NewsProviderPort)

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/council/council_news_provider.py`
- Test: `backend/tests/test_council_news_provider.py`

- [ ] **Step 1: Write failing test** — `backend/tests/test_council_news_provider.py`:
  ```python
  """CouncilNewsProvider — implements NewsProviderPort for the 4 pipelines."""
  from __future__ import annotations

  import json
  from datetime import date
  from unittest.mock import AsyncMock, MagicMock

  import pytest

  from daily_scheduler.domain.ports.llm_provider import LLMResult
  from daily_scheduler.infrastructure.adapters.claude.parser import parse_report_content
  from daily_scheduler.infrastructure.adapters.council.council_news_provider import (
      CouncilNewsProvider,
  )
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


  def _full_pm_payload() -> dict:
      return {
          "report_date": "2026-05-25",
          "market_summary": "ok",
          "alert_banner": "",
          "news_items": [], "causal_chains": [], "risk_matrix": [],
          "sector_analysis": [], "sentiment": [], "technicals": [],
          "recommendations": [{
              "ticker": "005930", "name": "Samsung", "market": "KOSPI",
              "direction": "LONG", "timeframe": "DAY",
              "entry_price": 70000, "target_price": 75000, "stop_loss": 68000,
              "sector": "semi", "rationale": "x", "causal_chain_summary": "y",
              "risk_reward_ratio": 2.5, "confidence": "high",
          }],
          "upcoming_events": [], "past_performance_commentary": "", "disclaimer": "x",
      }


  def _convergence_router() -> LLMRouter:
      claude = MagicMock()
      claude.submit = AsyncMock(return_value=LLMResult(
          text=json.dumps(_full_pm_payload()), model="opus", provider="claude-code",
          tokens_in=0, tokens_out=0, latency_ms=1, command_hash="a",
      ))
      codex = MagicMock()
      codex.submit = AsyncMock(return_value=LLMResult(
          text=json.dumps({
              "agreement_score": 0.95,
              "dimensions": {"logical_coherence": 1.0, "evidence_quality": 0.9,
                              "remaining_disagreement": "", "sharpening_questions": []},
              "false_consensus_detected": False, "false_consensus_reason": None,
          }),
          model="gpt-5-codex", provider="codex",
          tokens_in=0, tokens_out=0, latency_ms=1, command_hash="b",
      ))
      binding_repo = MagicMock(); binding_repo.get = MagicMock(return_value=None)
      return LLMRouter(claude_code=claude, codex=codex, binding_repo=binding_repo)


  @pytest.mark.asyncio
  async def test_generate_daily_report_returns_text_and_elapsed() -> None:
      memory = MagicMock(
          query_metadata=MagicMock(return_value=[]),
          traverse_tree=MagicMock(return_value=[]),
      )
      provider = CouncilNewsProvider(router=_convergence_router(), memory_store=memory)
      text, elapsed = await provider.generate_daily_report(
          report_date=date(2026, 5, 25),
          retrospective_context="x",
          weekly_lessons="",
          market_data="m",
          screening_data="s",
      )
      assert isinstance(text, str)
      assert elapsed >= 0
      parsed = parse_report_content(text)
      assert parsed is not None
      assert parsed.report_date == "2026-05-25"


  @pytest.mark.asyncio
  async def test_sync_wrapper_methods_present() -> None:
      """Existing pipeline code calls these via synchronous interface."""
      memory = MagicMock(
          query_metadata=MagicMock(return_value=[]),
          traverse_tree=MagicMock(return_value=[]),
      )
      provider = CouncilNewsProvider(router=_convergence_router(), memory_store=memory)
      # All four methods exist with the expected sync signature
      assert callable(provider.generate_daily_report)
      assert callable(provider.generate_weekly_report)
      assert callable(provider.generate_news_briefing)
      assert callable(provider.generate_global_news_briefing)


  def test_provider_implements_news_provider_port() -> None:
      """Quick structural check — the four method names exist."""
      memory = MagicMock()
      provider = CouncilNewsProvider(router=MagicMock(), memory_store=memory)
      for m in ("generate_daily_report", "generate_weekly_report",
                "generate_news_briefing", "generate_global_news_briefing"):
          assert hasattr(provider, m)
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_council_news_provider.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/council/council_news_provider.py`:
  ```python
  """CouncilNewsProvider — implements NewsProviderPort using the debate engine.

  This is the swap-in replacement for ClaudeNewsProvider. The four `generate_*`
  methods have identical signatures and return `tuple[str, float]` where the
  first element is JSON text that parse_report_content() consumes.
  """
  from __future__ import annotations

  import asyncio
  import time
  from datetime import date

  from daily_scheduler.domain.ports.memory_store import MemoryStorePort
  from daily_scheduler.infrastructure.adapters.council.verdict_serializer import (
      verdict_to_report_json,
  )
  from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter


  class CouncilNewsProvider:
      """Multi-agent council that satisfies NewsProviderPort."""

      def __init__(
          self,
          router: LLMRouter,
          memory_store: MemoryStorePort,
      ) -> None:
          self._router = router
          self._memory = memory_store

      def generate_daily_report(
          self,
          report_date: date,
          retrospective_context: str,
          weekly_lessons: str = "",
          market_data: str = "",
          screening_data: str = "",
      ) -> tuple[str, float]:
          return asyncio.run(self._run_pipeline(
              pipeline="daily",
              context={
                  "date": report_date.isoformat(),
                  "market_data": market_data,
                  "screening": screening_data,
                  "retrospective": retrospective_context,
                  "weekly_lessons": weekly_lessons,
                  "tickers": [], "regime": "neutral",
              },
          ))

      def generate_weekly_report(
          self,
          report_date: date,
          weekly_stats: str,
          detailed_performance: str,
          closed_rationales: str = "",
      ) -> tuple[str, float]:
          return asyncio.run(self._run_pipeline(
              pipeline="weekly",
              context={
                  "date": report_date.isoformat(),
                  "weekly_stats": weekly_stats,
                  "detailed_performance": detailed_performance,
                  "closed_rationales": closed_rationales,
                  "market_data": "", "screening": "",
                  "retrospective": "", "tickers": [], "regime": "weekly",
              },
          ))

      def generate_news_briefing(self, report_date: date) -> tuple[str, float]:
          return asyncio.run(self._run_pipeline(
              pipeline="news",
              context={"date": report_date.isoformat(),
                       "market_data": "", "screening": "",
                       "retrospective": "", "tickers": [], "regime": "kr"},
          ))

      def generate_global_news_briefing(self, report_date: date) -> tuple[str, float]:
          return asyncio.run(self._run_pipeline(
              pipeline="global-news",
              context={"date": report_date.isoformat(),
                       "market_data": "", "screening": "",
                       "retrospective": "", "tickers": [], "regime": "us"},
          ))

      async def _run_pipeline(
          self, pipeline: str, context: dict,
      ) -> tuple[str, float]:
          from daily_scheduler.application.use_cases.debate_engine import run_debate

          start = time.monotonic()
          graph = await run_debate(
              pipeline=pipeline,
              router=self._router,
              memory_store=self._memory,
              context=context,
              triggered_by="scheduler",
          )
          elapsed = time.monotonic() - start

          if graph.verdict is None:
              # Failed debate — emit a minimal valid envelope so the parser
              # doesn't crash; downstream will see an empty report and a
              # generic error email will be sent by the pipeline as today.
              from daily_scheduler.domain.entities.debate import DebateState, Verdict
              fallback = Verdict(
                  debate_id=graph.id,
                  consensus=DebateState.FAILED,
                  report_content_json={
                      "report_date": context.get("date", ""),
                      "market_summary": f"Debate failed: {graph.error or 'unknown'}",
                  },
                  recommendation_dicts=[],
              )
              return verdict_to_report_json(fallback), elapsed

          return verdict_to_report_json(graph.verdict), elapsed
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_council_news_provider.py -v
  ```
  Expected: 3 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/council/council_news_provider.py backend/tests/test_council_news_provider.py
  git commit -m "feat(council): add CouncilNewsProvider implementing NewsProviderPort"
  ```

---

## Task 16: Outcome linkage in CheckRecommendations

**Files:**
- Modify: `backend/src/daily_scheduler/application/use_cases/check_recommendations.py`
- Test: `backend/tests/test_check_recommendations.py` (add cases)

- [ ] **Step 1: Read the current file** to see the current `__init__` signature:
  ```bash
  cat backend/src/daily_scheduler/application/use_cases/check_recommendations.py
  ```

- [ ] **Step 2: Write the failing tests** — append to `backend/tests/test_check_recommendations.py`:
  ```python
  # --- memory outcome linkage (Plan 2) ---

  from datetime import datetime
  from unittest.mock import MagicMock

  from daily_scheduler.domain.entities.recommendation import Recommendation
  from daily_scheduler.application.use_cases.check_recommendations import (
      CheckRecommendations,
  )


  def test_check_calls_memory_update_outcome_when_target_hit(monkeypatch):
      """When a rec is closed with TARGET_HIT, memory.update_outcome is called."""
      rec = Recommendation(
          id=1, report_id=1, ticker="005930", name="Samsung",
          market="KOSPI", direction="LONG", timeframe="DAY",
          entry_price=70000, target_price=75000, stop_loss=68000,
          status="OPEN", created_at=datetime.now(),
      )
      # Attach memory_node_id so the use case knows which memory to update
      setattr(rec, "memory_node_id", "mem-1")

      rec_repo = MagicMock()
      rec_repo.get_open = MagicMock(return_value=[rec])

      def update(updated_rec):
          updated_rec.status = updated_rec.status  # ack
      rec_repo.update = MagicMock(side_effect=update)

      finance = MagicMock()
      finance.fetch_price = MagicMock(return_value={"price": 76000})

      memory = MagicMock()
      memory.update_outcome = MagicMock()

      uc = CheckRecommendations(rec_repo=rec_repo, finance=finance, memory_store=memory)
      n = uc.execute()
      assert n == 1
      memory.update_outcome.assert_called_once_with("mem-1", "TARGET_HIT")


  def test_memory_store_param_is_optional_for_backward_compat():
      """Old callers without memory still work."""
      rec_repo = MagicMock()
      rec_repo.get_open = MagicMock(return_value=[])
      finance = MagicMock()
      uc = CheckRecommendations(rec_repo=rec_repo, finance=finance)
      assert uc.execute() == 0
  ```

- [ ] **Step 3:** Run:
  ```bash
  cd backend && uv run pytest tests/test_check_recommendations.py -v
  ```
  Expected: 2 of the 2 new tests fail (constructor doesn't accept `memory_store`).

- [ ] **Step 4:** Modify `backend/src/daily_scheduler/application/use_cases/check_recommendations.py`:
  - Add `memory_store: MemoryStorePort | None = None` to `__init__`
  - In the closure-detection branch (where `status` is set to `TARGET_HIT` / `STOP_HIT` / `EXPIRED`), if `self._memory is not None` and `getattr(rec, "memory_node_id", None)` is truthy, call `self._memory.update_outcome(rec.memory_node_id, rec.status)`.
  - The call must be in a `try/except` and log on failure (memory outage must not break recommendation closing).

  Skeleton:
  ```python
  from daily_scheduler.domain.ports.memory_store import MemoryStorePort


  class CheckRecommendations:
      def __init__(
          self,
          rec_repo,
          finance,
          *,
          memory_store: MemoryStorePort | None = None,
      ) -> None:
          self._rec_repo = rec_repo
          self._finance = finance
          self._memory = memory_store

      def execute(self) -> int:
          # ... existing logic ...
          # after rec.status is set to TARGET_HIT/STOP_HIT/EXPIRED and rec_repo.update(rec)
          if self._memory is not None:
              memory_node_id = getattr(rec, "memory_node_id", None)
              if memory_node_id and rec.status in {"TARGET_HIT", "STOP_HIT", "EXPIRED"}:
                  try:
                      self._memory.update_outcome(memory_node_id, rec.status)
                  except Exception as e:
                      logger.warning(
                          "memory update_outcome failed for %s: %s", memory_node_id, e,
                      )
          return count
  ```

  Important: keep all existing logic intact. Add only the memory update path. The `Recommendation` domain entity needs a `memory_node_id` field — add it to the dataclass as `memory_node_id: str | None = None`.

- [ ] **Step 5:** Add `memory_node_id` to `backend/src/daily_scheduler/domain/entities/recommendation.py`:
  ```python
  @dataclass
  class Recommendation:
      # ... existing fields ...
      debate_id: str | None = None
      memory_node_id: str | None = None
  ```

- [ ] **Step 6:** Run:
  ```bash
  cd backend && uv run pytest tests/test_check_recommendations.py -v
  ```
  Expected: all pass (existing + 2 new).

- [ ] **Step 7:** Commit:
  ```bash
  git add backend/src/daily_scheduler/application/use_cases/check_recommendations.py backend/src/daily_scheduler/domain/entities/recommendation.py backend/tests/test_check_recommendations.py
  git commit -m "feat(application): wire memory.update_outcome when recommendation closes"
  ```

---

## Task 17: Wire CouncilNewsProvider into dependencies + add memory store factories

**Files:**
- Modify: `backend/src/daily_scheduler/infrastructure/dependencies.py`
- Test: `backend/tests/test_dependencies.py` (add cases)

- [ ] **Step 1: Write failing test** — append to `backend/tests/test_dependencies.py`:
  ```python
  # --- Plan 2: council wiring ---

  def test_get_news_provider_returns_council_provider(session_factory) -> None:
      """The factory now returns a CouncilNewsProvider, not ClaudeNewsProvider."""
      from daily_scheduler.infrastructure.adapters.council.council_news_provider import (
          CouncilNewsProvider,
      )
      from daily_scheduler.infrastructure.dependencies import get_news_provider

      sf, tmp_path, eng = session_factory
      provider = get_news_provider(session_factory=sf, engine=eng, memory_root=tmp_path / "mem")
      assert isinstance(provider, CouncilNewsProvider)


  def test_get_agent_binding_repo(session_factory) -> None:
      from daily_scheduler.infrastructure.adapters.persistence.agent_binding_repository import (
          SQLAlchemyAgentBindingRepository,
      )
      from daily_scheduler.infrastructure.dependencies import get_agent_binding_repo

      sf, _, _ = session_factory
      with sf() as s:
          repo = get_agent_binding_repo(s)
          assert isinstance(repo, SQLAlchemyAgentBindingRepository)
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_dependencies.py::test_get_news_provider_returns_council_provider tests/test_dependencies.py::test_get_agent_binding_repo -v
  ```
  Expected: ImportError on `get_agent_binding_repo`; the existing `get_news_provider()` returns the old `ClaudeNewsProvider`, so the first test fails on isinstance.

- [ ] **Step 3:** Modify `backend/src/daily_scheduler/infrastructure/dependencies.py`:

  Add (near other repo factories):
  ```python
  def get_agent_binding_repo(db: Session) -> SQLAlchemyAgentBindingRepository:
      """Create an agent_binding repository."""
      from daily_scheduler.infrastructure.adapters.persistence.agent_binding_repository import (
          SQLAlchemyAgentBindingRepository,
      )
      return SQLAlchemyAgentBindingRepository(db)
  ```

  **Critical change** — rewrite `get_news_provider` (changes the signature):
  ```python
  def get_news_provider(
      *,
      session_factory: Callable[[], Session],
      engine: Engine,
      memory_root: Path,
  ):
      """Build the multi-agent CouncilNewsProvider.

      Plan 2 replaces the legacy ClaudeNewsProvider here. The four pipeline
      methods retain their signatures, so RunDailyPipeline / RunWeeklyPipeline /
      RunNewsBriefingPipeline continue to work unchanged.
      """
      from daily_scheduler.infrastructure.adapters.council.council_news_provider import (
          CouncilNewsProvider,
      )
      from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter
      from daily_scheduler.infrastructure.adapters.persistence.agent_binding_repository import (
          SQLAlchemyAgentBindingRepository,
      )

      memory_store = get_memory_store(
          session_factory=session_factory, engine=engine, memory_root=memory_root,
      )
      # binding repo uses its own short-lived session
      session = session_factory()
      try:
          binding_repo = SQLAlchemyAgentBindingRepository(session)
          router = LLMRouter(
              claude_code=get_claude_code_provider(),
              codex=get_codex_provider(),
              binding_repo=binding_repo,
          )
          return CouncilNewsProvider(router=router, memory_store=memory_store)
      finally:
          # We do NOT close session here because the repo may be used later via
          # the router; the SQLAlchemy session is kept alive for the provider.
          pass
  ```

  Update each pipeline factory that previously called `get_news_provider()` with no args. The new signature requires `session_factory`, `engine`, `memory_root`. Adjust callers:

  ```python
  def get_daily_pipeline(db: Session) -> RunDailyPipeline:
      settings = get_settings()
      memory_root = settings.db_path.parent / "memory"
      sf = lambda: db.session.session_factory()  # or however the project derives this
      return RunDailyPipeline(
          report_repo=get_report_repo(db),
          rec_repo=get_rec_repo(db),
          retro_repo=get_retro_repo(db),
          price_repo=get_price_repo(db),
          finance=get_finance_provider(),
          news=get_news_provider(
              session_factory=lambda: db.session_factory()(),  # adjust per project
              engine=db.bind,
              memory_root=memory_root,
          ),
          email=get_email_sender(),
          renderer=get_renderer(),
      )
  ```

  **NOTE**: the exact derivation of `session_factory` and `engine` from the FastAPI-injected `Session` depends on the existing app setup. Read `backend/src/daily_scheduler/database.py` carefully — it likely has a `SessionLocal` or `session_factory` available. If `db.bind` doesn't give an Engine, use the `engine` variable from `database.py` directly (`from daily_scheduler.database import engine`).

- [ ] **Step 4:** Also pass `memory_store` to `CheckRecommendations` in the daily pipeline use case. Inside `RunDailyPipeline.execute`, the existing check_recommendations call now takes the memory store. Update its construction site (likely in `run_daily_pipeline.py`):
  - Look for `CheckRecommendations(self._rec_repo, self._finance)`
  - Change to `CheckRecommendations(self._rec_repo, self._finance, memory_store=self._memory_store)`
  - Add `memory_store: MemoryStorePort | None = None` to `RunDailyPipeline.__init__`
  - Wire it through from `get_daily_pipeline`.

- [ ] **Step 5:** Run full suite:
  ```bash
  cd backend && uv run pytest -v 2>&1 | tail -10
  ```
  Expected: all green. The existing PIPE-* tests continue to pass because the `NewsProviderPort` interface is preserved.

- [ ] **Step 6:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/dependencies.py backend/src/daily_scheduler/application/use_cases/run_daily_pipeline.py backend/tests/test_dependencies.py
  git commit -m "feat(infra): swap get_news_provider() to CouncilNewsProvider"
  ```

---

## Task 18: Persist debate to DB + link to recommendations

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/persistence/debate_repository.py`
- Create: `backend/src/daily_scheduler/domain/ports/debate_repository.py`
- Modify: `backend/src/daily_scheduler/infrastructure/adapters/council/council_news_provider.py` — after a debate finishes, persist it and link recommendations
- Test: `backend/tests/test_debate_repository.py`

This task ensures `DebateGraph` aggregates are persisted (for the UI in Plan 3 to read) and each `Recommendation` gets its `debate_id`+`memory_node_id` set so memory updates can flow on close.

- [ ] **Step 1: Write failing test** — `backend/tests/test_debate_repository.py`:
  ```python
  """Tests for DebateRepository — persists DebateGraph + Round + Speech."""
  from __future__ import annotations

  from datetime import datetime

  import pytest
  from sqlalchemy import create_engine
  from sqlalchemy.orm import Session

  from daily_scheduler.database import Base
  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.entities.debate import (
      ConsensusScore, DebateGraph, DebateState, Round, Speech, Verdict,
  )
  from daily_scheduler.infrastructure.adapters.persistence.debate_repository import (
      SQLAlchemyDebateRepository,
  )


  @pytest.fixture
  def session():
      eng = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(eng)
      with Session(eng) as s:
          yield s


  def _graph_with_round() -> DebateGraph:
      bull = Speech(
          agent_role=Role.BULL, text="b", structured_json={"direction": "BUY"},
          tokens_in=0, tokens_out=0, latency_ms=0, cli_command_hash="",
      )
      bear = Speech(
          agent_role=Role.BEAR, text="r", structured_json={"direction": "BUY"},
          tokens_in=0, tokens_out=0, latency_ms=0, cli_command_hash="",
      )
      score = ConsensusScore(
          rule_score=0.9, llm_score=0.85, false_consensus=False,
          next_round_questions=[], dimensions={"direction": 1.0},
      )
      rnd = Round(index=0, bull_speech=bull, bear_speech=bear, judge_score=score)
      verdict = Verdict(
          debate_id="d1", consensus=DebateState.CONVERGED,
          report_content_json={"recommendations": [{"ticker": "005930"}]},
          recommendation_dicts=[{"ticker": "005930"}],
      )
      return DebateGraph(
          id="d1", pipeline="daily", state=DebateState.CONVERGED,
          rounds=[rnd], analyst_reports=[{"role": "kr_fundamentals"}],
          verdict=verdict,
          started_at=datetime.now(), ended_at=datetime.now(),
          triggered_by="scheduler",
      )


  def test_save_persists_debate_round_speeches(session) -> None:
      repo = SQLAlchemyDebateRepository(session)
      g = _graph_with_round()
      repo.save(g)
      # Confirm DB rows exist
      from daily_scheduler.infrastructure.adapters.persistence.models import (
          DebateModel, RoundModel, SpeechModel,
      )
      assert session.get(DebateModel, "d1") is not None
      assert session.query(RoundModel).count() == 1
      assert session.query(SpeechModel).count() == 2


  def test_get_by_id(session) -> None:
      repo = SQLAlchemyDebateRepository(session)
      g = _graph_with_round()
      repo.save(g)
      loaded = repo.get("d1")
      assert loaded is not None
      assert loaded.id == "d1"
      assert loaded.state is DebateState.CONVERGED
      assert len(loaded.rounds) == 1


  def test_list_recent(session) -> None:
      repo = SQLAlchemyDebateRepository(session)
      for i in range(3):
          g = _graph_with_round()
          g.id = f"d{i}"
          if g.verdict:
              g.verdict.debate_id = f"d{i}"  # type: ignore[misc]
          repo.save(g)
      rows = list(repo.list_recent(limit=5))
      assert len(rows) == 3
  ```

- [ ] **Step 2:** Run:
  ```bash
  cd backend && uv run pytest tests/test_debate_repository.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create the port `backend/src/daily_scheduler/domain/ports/debate_repository.py`:
  ```python
  """Port for persisting DebateGraph aggregates."""
  from __future__ import annotations

  from collections.abc import Iterator
  from typing import Protocol

  from daily_scheduler.domain.entities.debate import DebateGraph


  class DebateRepositoryPort(Protocol):
      def save(self, graph: DebateGraph) -> None: ...
      def get(self, debate_id: str) -> DebateGraph | None: ...
      def list_recent(self, *, pipeline: str | None = None, limit: int = 50) -> Iterator[DebateGraph]: ...
  ```

  Create the adapter `backend/src/daily_scheduler/infrastructure/adapters/persistence/debate_repository.py`:
  ```python
  """SQLAlchemy adapter for DebateRepositoryPort."""
  from __future__ import annotations

  from collections.abc import Iterator
  from datetime import datetime

  from sqlalchemy.orm import Session
  from ulid import ULID

  from daily_scheduler.domain.entities.agent import Role
  from daily_scheduler.domain.entities.debate import (
      ConsensusScore, DebateGraph, DebateState, Round, Speech, Verdict,
  )
  from daily_scheduler.infrastructure.adapters.persistence.models import (
      DebateModel, RoundModel, SpeechModel,
  )


  class SQLAlchemyDebateRepository:
      def __init__(self, session: Session) -> None:
          self._s = session

      def save(self, graph: DebateGraph) -> None:
          d = DebateModel(
              id=graph.id, pipeline=graph.pipeline,
              state=graph.state.value,
              started_at=graph.started_at, ended_at=graph.ended_at,
              triggered_by=graph.triggered_by,
              verdict_json=(
                  graph.verdict.report_content_json if graph.verdict else None
              ),
              error=graph.error,
          )
          self._s.merge(d)

          # Rounds + speeches
          for rnd in graph.rounds:
              round_id = str(ULID())
              self._s.merge(RoundModel(
                  id=round_id, debate_id=graph.id, idx=rnd.index,
                  rule_score=rnd.judge_score.rule_score,
                  llm_score=rnd.judge_score.llm_score,
                  false_consensus=rnd.judge_score.false_consensus,
                  converged=rnd.judge_score.converged(rule_threshold=0.75, llm_threshold=0.70),
                  dimensions_json=dict(rnd.judge_score.dimensions),
                  next_round_questions_json=list(rnd.judge_score.next_round_questions),
                  created_at=datetime.now(),
              ))
              for speech in (rnd.bull_speech, rnd.bear_speech):
                  self._s.add(SpeechModel(
                      id=str(ULID()), debate_id=graph.id, round_id=round_id,
                      agent_role=speech.agent_role.value, text=speech.text,
                      structured_json=dict(speech.structured_json),
                      tokens_in=speech.tokens_in, tokens_out=speech.tokens_out,
                      latency_ms=speech.latency_ms,
                      cli_command_hash=speech.cli_command_hash,
                      created_at=datetime.now(),
                  ))
          self._s.commit()

      def get(self, debate_id: str) -> DebateGraph | None:
          d = self._s.get(DebateModel, debate_id)
          if d is None:
              return None
          rounds_rows = self._s.query(RoundModel).filter(
              RoundModel.debate_id == debate_id,
          ).order_by(RoundModel.idx).all()
          rounds = []
          for r in rounds_rows:
              speech_rows = self._s.query(SpeechModel).filter(
                  SpeechModel.round_id == r.id,
              ).all()
              bull = next((s for s in speech_rows if s.agent_role == "bull"), None)
              bear = next((s for s in speech_rows if s.agent_role == "bear"), None)
              if bull is None or bear is None:
                  continue
              rounds.append(Round(
                  index=r.idx,
                  bull_speech=self._row_to_speech(bull),
                  bear_speech=self._row_to_speech(bear),
                  judge_score=ConsensusScore(
                      rule_score=r.rule_score, llm_score=r.llm_score,
                      false_consensus=r.false_consensus,
                      next_round_questions=list(r.next_round_questions_json or []),
                      dimensions=dict(r.dimensions_json or {}),
                  ),
              ))
          verdict: Verdict | None = None
          if d.verdict_json is not None:
              verdict = Verdict(
                  debate_id=d.id, consensus=DebateState(d.state),
                  report_content_json=dict(d.verdict_json),
                  recommendation_dicts=list(d.verdict_json.get("recommendations", [])),
              )
          return DebateGraph(
              id=d.id, pipeline=d.pipeline, state=DebateState(d.state),
              rounds=rounds, analyst_reports=[], verdict=verdict,
              started_at=d.started_at, ended_at=d.ended_at,
              triggered_by=d.triggered_by, error=d.error,
          )

      def list_recent(
          self, *, pipeline: str | None = None, limit: int = 50,
      ) -> Iterator[DebateGraph]:
          q = self._s.query(DebateModel)
          if pipeline:
              q = q.filter(DebateModel.pipeline == pipeline)
          for row in q.order_by(DebateModel.started_at.desc()).limit(limit).all():
              g = self.get(row.id)
              if g is not None:
                  yield g

      @staticmethod
      def _row_to_speech(row: SpeechModel) -> Speech:
          return Speech(
              agent_role=Role(row.agent_role),
              text=row.text,
              structured_json=dict(row.structured_json or {}),
              tokens_in=row.tokens_in, tokens_out=row.tokens_out,
              latency_ms=row.latency_ms,
              cli_command_hash=row.cli_command_hash,
          )
  ```

- [ ] **Step 4:** Run:
  ```bash
  cd backend && uv run pytest tests/test_debate_repository.py -v
  ```
  Expected: 3 passed.

- [ ] **Step 5:** Wire the repo into the `CouncilNewsProvider`. Modify the provider's `__init__` to take an optional `debate_repo: DebateRepositoryPort | None = None`. After `run_debate` produces the graph, if a repo is provided, call `repo.save(graph)`. Add a factory wiring this in `dependencies.py`. Failures of repo.save must not fail the report (best-effort), so wrap in try/except + log.

- [ ] **Step 6:** Commit:
  ```bash
  git add backend/src/daily_scheduler/domain/ports/debate_repository.py backend/src/daily_scheduler/infrastructure/adapters/persistence/debate_repository.py backend/src/daily_scheduler/infrastructure/adapters/council/council_news_provider.py backend/src/daily_scheduler/infrastructure/dependencies.py backend/tests/test_debate_repository.py
  git commit -m "feat(persistence): persist DebateGraph + wire into CouncilNewsProvider"
  ```

---

## Task 19: Full regression + static analysis

**Files:** none

- [ ] **Step 1:** Full pytest:
  ```bash
  cd backend && uv run pytest -v 2>&1 | tail -10
  ```
  Expected: all existing + all Plan 2 tests pass. **Zero regression** on PIPE/REC/RPT/RETRO/API.

- [ ] **Step 2:** ruff lint:
  ```bash
  cd backend && uv run ruff check src tests
  ```
  Fix any issues inline.

- [ ] **Step 3:** ruff format:
  ```bash
  cd backend && uv run ruff format --check src tests
  ```

- [ ] **Step 4:** pyrefly:
  ```bash
  cd backend && uv run pyrefly check src
  ```

- [ ] **Step 5:** pylint on new modules:
  ```bash
  cd backend && uv run pylint src/daily_scheduler/infrastructure/adapters/council src/daily_scheduler/infrastructure/adapters/debate src/daily_scheduler/domain/entities/agent.py src/daily_scheduler/domain/entities/debate.py src/daily_scheduler/domain/ports/agent_binding_repo.py src/daily_scheduler/domain/ports/debate_repository.py src/daily_scheduler/application/use_cases/debate_engine.py src/daily_scheduler/application/use_cases/memory_injection.py
  ```
  Expected: 10.00/10. Fix any warnings.

- [ ] **Step 6:** Tag:
  ```bash
  git tag -a plan-2-debate-engine -m "Plan 2 complete: multi-agent debate engine + pipeline integration"
  ```

---

## Self-Review Notes

**Spec coverage:**
- `AGENT-01..06` — Tasks 2, 5, 11, 17 (role definition, binding override via UI in Plan 3, snapshot-at-start in debate engine)
- `DEBATE-01..10` — Tasks 7-13 (analyst pool, debate loop, max rounds, sequential weekly, persistence, ReportContent compatibility, semaphore via Plan 1's pool)
- `JUDGE-01..08` — Task 9 (hybrid rule+LLM, AND threshold, false consensus, fixtures, different-provider default for judge, constants)
- `MEM-08` (empty-memory OK) — Task 12
- `DATA-05` (legacy recs preserved) — Task 4 makes new columns nullable; existing recs untouched

**Out of scope (handled later):**
- Live SSE streaming → Plan 3
- UI pages → Plan 3
- Multica integration → Plan 4
- Full E2E + performance budget → Plan 5

**Risk flags:**
- The dependency injection rewiring (Task 17) touches `RunDailyPipeline.__init__`. Run the full suite immediately after. If the SQLAlchemy session factory derivation is awkward, expose a module-level `session_factory` from `database.py` so factories can import it directly rather than going through `db.bind`.
- LangGraph proper is NOT yet wired (Task 13 uses a hand-written orchestrator). Plan 3 will revisit this if SSE checkpoint replay needs the StateGraph API.

---

## Execution Handoff

The orchestrator proceeds with subagent-driven implementation per the user's "끝까지 알아서" instruction.
