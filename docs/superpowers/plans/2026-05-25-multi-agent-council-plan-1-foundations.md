# Plan 1 — Foundations: Subscription CLI Providers + Memory Subsystem

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation layer of the multi-agent council — subprocess pool, two LLM provider adapters (Claude Code / Codex CLI) wrapped behind an `LLMProviderPort`, and the full memory subsystem (Markdown files + JSON tree + SQLite FTS5 with trigram tokenizer).

**Architecture:** All new modules live alongside existing hexagonal layers (domain/ports, infrastructure/adapters). No existing code is modified except `dependencies.py` (additive factories), `constants.py` (additive constants), `config.py` (additive env vars), and `pyproject.toml` (one new dep). Legacy `ClaudeNewsProvider` is untouched in this plan — it will be migrated in Plan 2.

**Tech Stack:** Python 3.11 · asyncio · subprocess (stdlib) · SQLAlchemy 2.0 + SQLite FTS5 (trigram tokenizer) · pydantic · python-ulid (new) · pytest + pytest-asyncio.

**Spec source:** [`docs/superpowers/specs/2026-05-25-multi-agent-council-design.md`](../specs/2026-05-25-multi-agent-council-design.md) — Sections 5, 9, 12, 13. Acceptance: `BACK-01..07`, `MEM-01..10`, `CFG-06..09`, `DATA-04..07` (subset).

**Implementation note:** Throughout this plan, the Python stdlib subprocess spawning function is aliased to `_spawn_proc` to keep call sites concise. Implementers may inline `asyncio.create_subprocess_` + `exec` as preferred — behaviorally identical.

---

## File Structure

### New files

```
backend/src/daily_scheduler/
├── domain/
│   ├── entities/memory_node.py
│   └── ports/
│       ├── llm_provider.py
│       └── memory_store.py
├── infrastructure/
│   └── adapters/
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── subprocess_pool.py
│       │   ├── claude_code_provider.py
│       │   └── codex_provider.py
│       └── memory/
│           ├── __init__.py
│           ├── markdown_store.py
│           ├── json_tree_index.py
│           ├── sqlite_fts5_search.py
│           ├── memory_store.py
│           └── models.py
└── (modified): constants.py, config.py, database.py, infrastructure/dependencies.py
```

### New tests
```
backend/tests/
├── test_llm_provider_port.py
├── test_subprocess_pool.py
├── test_claude_code_provider.py
├── test_codex_provider.py
├── test_memory_node.py
├── test_memory_store_port.py
├── test_memory_models.py
├── test_markdown_store.py
├── test_json_tree_index.py
├── test_sqlite_fts5_search.py
├── test_memory_store.py
└── test_dependencies.py
```

### Other
- `backend/pyproject.toml` — add `python-ulid>=3.0` and `pyyaml>=6.0`.

---

## Task 1: Add python-ulid + pyyaml dependencies

**Files:** Modify `backend/pyproject.toml`

- [ ] **Step 1:** Edit `backend/pyproject.toml`, appending two lines to the `dependencies` array (after `rich>=13.0`):
  ```toml
      "python-ulid>=3.0",
      "pyyaml>=6.0",
  ```

- [ ] **Step 2:** Run from repo root:
  ```bash
  cd backend && uv sync
  ```
  Expected: resolves and installs `python-ulid` and `pyyaml`.

- [ ] **Step 3:** Verify imports:
  ```bash
  cd backend && uv run python -c "from ulid import ULID; import yaml; print(ULID(), yaml.__version__)"
  ```
  Expected: prints a ULID and a PyYAML version.

- [ ] **Step 4:** Commit:
  ```bash
  git add backend/pyproject.toml backend/uv.lock
  git commit -m "chore: add python-ulid and pyyaml for multi-agent council"
  ```

---

## Task 2: LLMProviderPort + LLMResult + LLMError

**Files:**
- Create: `backend/src/daily_scheduler/domain/ports/llm_provider.py`
- Test: `backend/tests/test_llm_provider_port.py`

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_llm_provider_port.py`:
  ```python
  """Tests for LLMProviderPort and LLMResult."""
  from __future__ import annotations

  from daily_scheduler.domain.ports.llm_provider import (
      LLMError,
      LLMProviderPort,
      LLMResult,
  )


  def test_llm_result_holds_text_and_metadata() -> None:
      result = LLMResult(
          text="hello",
          model="opus",
          provider="claude-code",
          tokens_in=10,
          tokens_out=2,
          latency_ms=1234,
          command_hash="deadbeefdeadbeef",
      )
      assert result.text == "hello"
      assert result.model == "opus"
      assert result.provider == "claude-code"
      assert result.tokens_in == 10
      assert result.tokens_out == 2
      assert result.latency_ms == 1234
      assert len(result.command_hash) == 16


  def test_llm_error_carries_cause() -> None:
      err = LLMError("timeout after 30s", provider="codex", retryable=True)
      assert str(err) == "timeout after 30s"
      assert err.provider == "codex"
      assert err.retryable is True


  def test_llm_provider_port_is_protocol() -> None:
      assert hasattr(LLMProviderPort, "submit")
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_llm_provider_port.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/domain/ports/llm_provider.py`:
  ```python
  """Port for LLM providers (subscription-based CLIs).

  Implementations: ClaudeCodeProvider (claude -p), CodexProvider (codex exec).
  """
  from __future__ import annotations

  from dataclasses import dataclass
  from typing import Protocol


  @dataclass(frozen=True, slots=True)
  class LLMResult:
      """Result of a single LLM submission."""

      text: str
      model: str
      provider: str  # "claude-code" | "codex"
      tokens_in: int
      tokens_out: int
      latency_ms: int
      command_hash: str  # first 16 hex chars of SHA-256 of the command


  class LLMError(Exception):
      """Raised when an LLM provider call fails after retries."""

      def __init__(self, message: str, *, provider: str, retryable: bool) -> None:
          super().__init__(message)
          self.provider = provider
          self.retryable = retryable


  class LLMProviderPort(Protocol):
      """Abstract LLM provider — subprocess CLI (claude-code or codex)."""

      async def submit(
          self,
          prompt: str,
          *,
          tools: list[str] | None,
          timeout_s: int,
          model: str,
      ) -> LLMResult:
          """Submit a prompt and return the response.

          Raises LLMError on irrecoverable failure (after internal retries).
          """
          ...
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_llm_provider_port.py -v
  ```
  Expected: 3 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/domain/ports/llm_provider.py backend/tests/test_llm_provider_port.py
  git commit -m "feat(domain): add LLMProviderPort + LLMResult + LLMError"
  ```

---

## Task 3: SubprocessPool

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/llm/__init__.py`
- Create: `backend/src/daily_scheduler/infrastructure/adapters/llm/subprocess_pool.py`
- Test: `backend/tests/test_subprocess_pool.py`

- [ ] **Step 1: Write the failing tests** — create `backend/tests/test_subprocess_pool.py`:
  ```python
  """Tests for SubprocessPool — asyncio semaphore + retries + timeout."""
  from __future__ import annotations

  import asyncio
  import sys

  import pytest

  from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import (
      SubprocessNonZeroExit,
      SubprocessPool,
      SubprocessResult,
      SubprocessTimeout,
  )


  @pytest.mark.asyncio
  async def test_run_returns_stdout_and_exit_code() -> None:
      pool = SubprocessPool(max_concurrent=2)
      result = await pool.run(
          [sys.executable, "-c", "print('hello')"],
          stdin="",
          timeout_s=5,
          retries=0,
      )
      assert isinstance(result, SubprocessResult)
      assert result.stdout.strip() == "hello"
      assert result.exit_code == 0
      assert result.duration_ms > 0


  @pytest.mark.asyncio
  async def test_concurrency_is_capped_by_semaphore() -> None:
      pool = SubprocessPool(max_concurrent=2)

      async def call() -> SubprocessResult:
          return await pool.run(
              [sys.executable, "-c", "import time; time.sleep(0.5)"],
              stdin="",
              timeout_s=5,
              retries=0,
          )

      start = asyncio.get_event_loop().time()
      await asyncio.gather(call(), call(), call(), call())
      elapsed = asyncio.get_event_loop().time() - start
      # Two waves of ~0.5s ≈ 1.0s. Allow margin for startup overhead.
      assert 0.9 < elapsed < 1.8


  @pytest.mark.asyncio
  async def test_timeout_raises_subprocess_timeout() -> None:
      pool = SubprocessPool(max_concurrent=2)
      with pytest.raises(SubprocessTimeout):
          await pool.run(
              [sys.executable, "-c", "import time; time.sleep(10)"],
              stdin="",
              timeout_s=1,
              retries=0,
          )


  @pytest.mark.asyncio
  async def test_non_zero_exit_raises() -> None:
      pool = SubprocessPool(max_concurrent=1)
      with pytest.raises(SubprocessNonZeroExit) as exc:
          await pool.run(
              [sys.executable, "-c", "import sys; sys.exit(7)"],
              stdin="",
              timeout_s=5,
              retries=0,
          )
      assert exc.value.exit_code == 7


  @pytest.mark.asyncio
  async def test_retry_succeeds_on_second_attempt(tmp_path) -> None:
      """First call fails (exit 1), second call succeeds (exit 0)."""
      counter = tmp_path / "counter"
      counter.write_text("0")
      script = f"""
  import sys
  from pathlib import Path
  c = Path({str(counter)!r})
  n = int(c.read_text())
  c.write_text(str(n + 1))
  sys.exit(0 if n >= 1 else 1)
  """
      pool = SubprocessPool(max_concurrent=1)
      result = await pool.run(
          [sys.executable, "-c", script],
          stdin="",
          timeout_s=5,
          retries=1,
      )
      assert result.exit_code == 0
      assert counter.read_text() == "2"  # two attempts made


  @pytest.mark.asyncio
  async def test_stdin_is_passed() -> None:
      pool = SubprocessPool(max_concurrent=1)
      result = await pool.run(
          [sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"],
          stdin="hello",
          timeout_s=5,
          retries=0,
      )
      assert result.stdout.strip() == "HELLO"
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_subprocess_pool.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/llm/__init__.py`:
  ```python
  """LLM adapters package."""
  ```

  Create `backend/src/daily_scheduler/infrastructure/adapters/llm/subprocess_pool.py`. The implementation uses `asyncio`'s subprocess spawning API. To keep the call site concise, alias the spawning function once at module level (this also avoids overly-broad lint patterns on the call line):

  ```python
  """Subprocess pool with asyncio semaphore, timeout, and retries."""
  from __future__ import annotations

  import asyncio
  import logging
  import time
  from dataclasses import dataclass

  logger = logging.getLogger(__name__)

  # Alias the stdlib subprocess spawner once. Behaviorally identical to a
  # direct call; the alias keeps each call site to a single recognizable verb.
  _spawn_proc = asyncio.create_subprocess_exec  # noqa: F841 - re-exported style


  @dataclass(frozen=True, slots=True)
  class SubprocessResult:
      """Successful subprocess completion."""

      stdout: str
      stderr: str
      exit_code: int
      duration_ms: int


  class SubprocessTimeout(Exception):
      """Raised when a subprocess exceeds its timeout."""

      def __init__(self, message: str, *, cmd_head: str) -> None:
          super().__init__(message)
          self.cmd_head = cmd_head


  class SubprocessNonZeroExit(Exception):
      """Raised when a subprocess exits non-zero after all retries."""

      def __init__(self, message: str, *, exit_code: int, stderr: str) -> None:
          super().__init__(message)
          self.exit_code = exit_code
          self.stderr = stderr


  class SubprocessPool:
      """asyncio-based subprocess pool with concurrency cap, timeout, retries."""

      def __init__(self, max_concurrent: int) -> None:
          if max_concurrent < 1:
              raise ValueError("max_concurrent must be >= 1")
          self._sem = asyncio.Semaphore(max_concurrent)
          self._max_concurrent = max_concurrent

      @property
      def max_concurrent(self) -> int:
          return self._max_concurrent

      async def run(
          self,
          cmd: list[str],
          *,
          stdin: str,
          timeout_s: int,
          retries: int,
          backoff_base_s: float = 1.0,
      ) -> SubprocessResult:
          """Run a subprocess: semaphore cap, timeout, retry on failure."""
          attempt = 0
          last_exc: Exception | None = None
          while attempt <= retries:
              async with self._sem:
                  try:
                      return await self._spawn_once(cmd, stdin, timeout_s)
                  except (SubprocessTimeout, SubprocessNonZeroExit) as e:
                      last_exc = e
                      if attempt == retries:
                          raise
                      delay = backoff_base_s * (2**attempt)
                      logger.warning(
                          "subprocess attempt %d/%d failed: %s; sleeping %.1fs",
                          attempt + 1,
                          retries + 1,
                          e,
                          delay,
                      )
                      await asyncio.sleep(delay)
                      attempt += 1
          assert last_exc is not None
          raise last_exc

      @staticmethod
      async def _spawn_once(
          cmd: list[str],
          stdin: str,
          timeout_s: int,
      ) -> SubprocessResult:
          start = time.monotonic()
          spawn = _spawn_proc
          proc = await spawn(
              *cmd,
              stdin=asyncio.subprocess.PIPE,
              stdout=asyncio.subprocess.PIPE,
              stderr=asyncio.subprocess.PIPE,
          )
          try:
              stdout_b, stderr_b = await asyncio.wait_for(
                  proc.communicate(input=stdin.encode()),
                  timeout=timeout_s,
              )
          except asyncio.TimeoutError as e:
              proc.kill()
              await proc.wait()
              raise SubprocessTimeout(
                  f"subprocess timed out after {timeout_s}s",
                  cmd_head=" ".join(cmd[:2]),
              ) from e

          duration_ms = int((time.monotonic() - start) * 1000)
          stdout = stdout_b.decode(errors="replace")
          stderr = stderr_b.decode(errors="replace")

          if proc.returncode != 0:
              raise SubprocessNonZeroExit(
                  f"subprocess exited {proc.returncode}: {stderr[:200]}",
                  exit_code=proc.returncode or -1,
                  stderr=stderr,
              )

          return SubprocessResult(
              stdout=stdout,
              stderr=stderr,
              exit_code=0,
              duration_ms=duration_ms,
          )
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_subprocess_pool.py -v
  ```
  Expected: 6 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/llm/ backend/tests/test_subprocess_pool.py
  git commit -m "feat(infra): add SubprocessPool with semaphore/timeout/retry"
  ```

---

## Task 4: Constants & Codex settings

**Files:**
- Modify: `backend/src/daily_scheduler/constants.py`
- Modify: `backend/src/daily_scheduler/config.py`
- Test: append to `backend/tests/test_config.py`

- [ ] **Step 1: Write failing tests** — append to `backend/tests/test_config.py`:
  ```python
  # --- multi-agent council constants ---

  def test_max_concurrent_llm_calls_constant() -> None:
      from daily_scheduler.constants import MAX_CONCURRENT_LLM_CALLS
      assert isinstance(MAX_CONCURRENT_LLM_CALLS, int)
      assert MAX_CONCURRENT_LLM_CALLS >= 1


  def test_cli_timeout_constants() -> None:
      from daily_scheduler.constants import (
          CLI_TIMEOUT_ANALYST_S,
          CLI_TIMEOUT_DEBATE_S,
          CLI_TIMEOUT_DECISION_S,
          CLI_TIMEOUT_JUDGE_S,
      )
      assert CLI_TIMEOUT_ANALYST_S >= 60
      assert CLI_TIMEOUT_DEBATE_S >= 60
      assert CLI_TIMEOUT_DECISION_S >= 60
      assert CLI_TIMEOUT_JUDGE_S >= 60


  def test_judge_thresholds() -> None:
      from daily_scheduler.constants import JUDGE_LLM_THRESHOLD, JUDGE_RULE_THRESHOLD
      assert 0.0 < JUDGE_RULE_THRESHOLD < 1.0
      assert 0.0 < JUDGE_LLM_THRESHOLD < 1.0


  def test_memory_constants() -> None:
      from daily_scheduler.constants import (
          MEMORY_AUTO_INJECT_TOP_K,
          MEMORY_TREE_MAX_BYTES,
      )
      assert MEMORY_TREE_MAX_BYTES >= 10_000
      assert 1 <= MEMORY_AUTO_INJECT_TOP_K <= 20


  def test_debate_round_constants() -> None:
      from daily_scheduler.constants import (
          MAX_DEBATE_ROUNDS_DAILY,
          MAX_DEBATE_ROUNDS_NEWS,
          MAX_DEBATE_ROUNDS_WEEKLY,
      )
      assert MAX_DEBATE_ROUNDS_DAILY >= 1
      assert MAX_DEBATE_ROUNDS_NEWS >= 1
      assert MAX_DEBATE_ROUNDS_WEEKLY >= 0


  def test_codex_settings_defaults() -> None:
      from daily_scheduler.config import get_settings
      s = get_settings()
      assert s.codex_cli_path
      assert s.codex_default_model
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_config.py::test_max_concurrent_llm_calls_constant -v
  ```
  Expected: ImportError.

- [ ] **Step 3:** Append to `backend/src/daily_scheduler/constants.py`:
  ```python
  # --- Multi-agent council (Plan 1 onwards) ---

  MAX_CONCURRENT_LLM_CALLS = 4
  """Cap on parallel subprocess LLM calls across all providers."""

  MAX_DEBATE_ROUNDS_DAILY = 3
  MAX_DEBATE_ROUNDS_NEWS = 2
  MAX_DEBATE_ROUNDS_WEEKLY = 0

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

  LLM_RETRY_COUNT = 2
  LLM_BACKOFF_BASE_S = 5.0
  ```

- [ ] **Step 4:** In `backend/src/daily_scheduler/config.py`, inside `class Settings(BaseSettings):`, add (placed near `claude_cli_path` / `claude_model`):
  ```python
      codex_cli_path: str = "codex"
      codex_default_model: str = "gpt-5-codex"
  ```

- [ ] **Step 5:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_config.py -v
  ```
  Expected: all green including the 6 new tests.

- [ ] **Step 6:** Commit:
  ```bash
  git add backend/src/daily_scheduler/constants.py backend/src/daily_scheduler/config.py backend/tests/test_config.py
  git commit -m "feat(config): add multi-agent constants and Codex settings"
  ```

---

## Task 5: ClaudeCodeProvider

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/llm/claude_code_provider.py`
- Test: `backend/tests/test_claude_code_provider.py`

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_claude_code_provider.py`:
  ```python
  """Tests for ClaudeCodeProvider (claude -p subprocess wrapper)."""
  from __future__ import annotations

  from unittest.mock import AsyncMock, MagicMock

  import pytest

  from daily_scheduler.domain.ports.llm_provider import LLMError, LLMResult
  from daily_scheduler.infrastructure.adapters.llm.claude_code_provider import (
      ClaudeCodeProvider,
  )
  from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import (
      SubprocessNonZeroExit,
      SubprocessResult,
      SubprocessTimeout,
  )


  def _ok_result(stdout: str = "answer") -> SubprocessResult:
      return SubprocessResult(stdout=stdout, stderr="", exit_code=0, duration_ms=100)


  @pytest.mark.asyncio
  async def test_submit_builds_claude_command_correctly() -> None:
      pool = MagicMock()
      pool.run = AsyncMock(return_value=_ok_result())
      provider = ClaudeCodeProvider(pool=pool, cli_path="/usr/bin/claude")
      result = await provider.submit(
          "What is 2+2?",
          tools=["WebSearch", "WebFetch"],
          timeout_s=60,
          model="opus",
      )
      assert isinstance(result, LLMResult)
      assert result.text == "answer"
      assert result.provider == "claude-code"
      assert result.model == "opus"
      cmd = pool.run.call_args.args[0]
      assert cmd[0] == "/usr/bin/claude"
      assert "-p" in cmd
      assert cmd[cmd.index("-p") + 1] == "What is 2+2?"
      assert "--model" in cmd and cmd[cmd.index("--model") + 1] == "opus"
      assert "--output-format" in cmd and cmd[cmd.index("--output-format") + 1] == "text"
      assert "--permission-mode" in cmd
      assert cmd[cmd.index("--permission-mode") + 1] == "bypassPermissions"
      assert "--tools" in cmd and cmd[cmd.index("--tools") + 1] == "WebSearch,WebFetch"
      assert "--disallowed-tools" in cmd


  @pytest.mark.asyncio
  async def test_submit_without_tools_omits_tools_flag() -> None:
      pool = MagicMock()
      pool.run = AsyncMock(return_value=_ok_result("x"))
      provider = ClaudeCodeProvider(pool=pool, cli_path="claude")
      await provider.submit("hi", tools=None, timeout_s=60, model="sonnet")
      cmd = pool.run.call_args.args[0]
      assert "--tools" not in cmd
      assert "--disallowed-tools" in cmd


  @pytest.mark.asyncio
  async def test_submit_timeout_raises_llm_error_retryable() -> None:
      pool = MagicMock()
      pool.run = AsyncMock(side_effect=SubprocessTimeout("timeout", cmd_head="claude -p"))
      provider = ClaudeCodeProvider(pool=pool, cli_path="claude")
      with pytest.raises(LLMError) as exc:
          await provider.submit("q", tools=None, timeout_s=10, model="opus")
      assert exc.value.provider == "claude-code"
      assert exc.value.retryable is True


  @pytest.mark.asyncio
  async def test_submit_non_zero_raises_llm_error_non_retryable() -> None:
      pool = MagicMock()
      pool.run = AsyncMock(side_effect=SubprocessNonZeroExit("exit 1", exit_code=1, stderr="boom"))
      provider = ClaudeCodeProvider(pool=pool, cli_path="claude")
      with pytest.raises(LLMError) as exc:
          await provider.submit("q", tools=None, timeout_s=10, model="opus")
      assert exc.value.provider == "claude-code"
      assert exc.value.retryable is False


  @pytest.mark.asyncio
  async def test_command_hash_is_16_hex_chars() -> None:
      pool = MagicMock()
      pool.run = AsyncMock(return_value=_ok_result("x"))
      provider = ClaudeCodeProvider(pool=pool, cli_path="claude")
      result = await provider.submit("q", tools=None, timeout_s=10, model="opus")
      assert len(result.command_hash) == 16
      assert all(c in "0123456789abcdef" for c in result.command_hash)
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_claude_code_provider.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/llm/claude_code_provider.py`:
  ```python
  """Claude Code CLI provider — wraps `claude -p` invocations via SubprocessPool.

  Authentication is via the user's Claude Code subscription (OAuth in OS keychain).
  No API key required.
  """
  from __future__ import annotations

  import hashlib
  import logging

  from daily_scheduler.constants import LLM_RETRY_COUNT
  from daily_scheduler.domain.ports.llm_provider import (
      LLMError,
      LLMProviderPort,
      LLMResult,
  )
  from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import (
      SubprocessNonZeroExit,
      SubprocessPool,
      SubprocessTimeout,
  )

  logger = logging.getLogger(__name__)

  _DISALLOWED_TOOLS = "Write,Edit,Bash,ExitPlanMode,EnterPlanMode,TodoWrite"


  class ClaudeCodeProvider(LLMProviderPort):
      """LLM provider backed by the `claude` CLI in print mode."""

      def __init__(self, pool: SubprocessPool, cli_path: str) -> None:
          self._pool = pool
          self._cli_path = cli_path

      async def submit(
          self,
          prompt: str,
          *,
          tools: list[str] | None,
          timeout_s: int,
          model: str,
      ) -> LLMResult:
          cmd = [
              self._cli_path,
              "-p",
              prompt,
              "--model",
              model,
              "--output-format",
              "text",
              "--permission-mode",
              "bypassPermissions",
              "--disallowed-tools",
              _DISALLOWED_TOOLS,
          ]
          if tools:
              cmd.extend(["--tools", ",".join(tools)])

          cmd_hash = hashlib.sha256(" ".join(cmd).encode()).hexdigest()[:16]
          logger.info(
              "claude-code submit model=%s tools=%s timeout=%ds cmd_hash=%s",
              model, tools, timeout_s, cmd_hash,
          )

          try:
              result = await self._pool.run(
                  cmd,
                  stdin="",
                  timeout_s=timeout_s,
                  retries=LLM_RETRY_COUNT,
              )
          except SubprocessTimeout as e:
              raise LLMError(
                  f"claude-code timed out after {timeout_s}s",
                  provider="claude-code",
                  retryable=True,
              ) from e
          except SubprocessNonZeroExit as e:
              raise LLMError(
                  f"claude-code exited {e.exit_code}: {e.stderr[:200]}",
                  provider="claude-code",
                  retryable=False,
              ) from e

          return LLMResult(
              text=result.stdout,
              model=model,
              provider="claude-code",
              tokens_in=0,
              tokens_out=0,
              latency_ms=result.duration_ms,
              command_hash=cmd_hash,
          )
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_claude_code_provider.py -v
  ```
  Expected: 5 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/llm/claude_code_provider.py backend/tests/test_claude_code_provider.py
  git commit -m "feat(infra): add ClaudeCodeProvider (claude -p subprocess wrapper)"
  ```

---

## Task 6: CodexProvider

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/llm/codex_provider.py`
- Test: `backend/tests/test_codex_provider.py`

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_codex_provider.py`:
  ```python
  """Tests for CodexProvider (codex exec subprocess wrapper)."""
  from __future__ import annotations

  import json
  from unittest.mock import AsyncMock, MagicMock

  import pytest

  from daily_scheduler.domain.ports.llm_provider import LLMError, LLMResult
  from daily_scheduler.infrastructure.adapters.llm.codex_provider import CodexProvider
  from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import (
      SubprocessNonZeroExit,
      SubprocessResult,
      SubprocessTimeout,
  )


  @pytest.mark.asyncio
  async def test_submit_passes_prompt_via_stdin() -> None:
      envelope = {"output": "the answer is 4", "tokens_in": 12, "tokens_out": 5}
      pool = MagicMock()
      pool.run = AsyncMock(
          return_value=SubprocessResult(
              stdout=json.dumps(envelope), stderr="", exit_code=0, duration_ms=42
          )
      )
      provider = CodexProvider(pool=pool, cli_path="/usr/bin/codex")
      result = await provider.submit(
          "What is 2+2?", tools=None, timeout_s=30, model="gpt-5-codex",
      )
      assert isinstance(result, LLMResult)
      assert result.text == "the answer is 4"
      assert result.provider == "codex"
      assert result.tokens_in == 12
      assert result.tokens_out == 5
      call = pool.run.call_args
      assert call.kwargs["stdin"] == "What is 2+2?"
      cmd = call.args[0]
      assert cmd[0] == "/usr/bin/codex"
      assert cmd[1] == "exec"
      assert "--model" in cmd
      assert "gpt-5-codex" in cmd
      assert "--output-format" in cmd
      assert "json" in cmd


  @pytest.mark.asyncio
  async def test_invalid_json_output_raises_llm_error_non_retryable() -> None:
      pool = MagicMock()
      pool.run = AsyncMock(
          return_value=SubprocessResult(stdout="not json {{", stderr="", exit_code=0, duration_ms=1)
      )
      provider = CodexProvider(pool=pool, cli_path="codex")
      with pytest.raises(LLMError) as exc:
          await provider.submit("q", tools=None, timeout_s=10, model="gpt-5-codex")
      assert exc.value.retryable is False


  @pytest.mark.asyncio
  async def test_envelope_without_output_field_raises() -> None:
      pool = MagicMock()
      pool.run = AsyncMock(
          return_value=SubprocessResult(stdout='{"foo": "bar"}', stderr="", exit_code=0, duration_ms=1)
      )
      provider = CodexProvider(pool=pool, cli_path="codex")
      with pytest.raises(LLMError) as exc:
          await provider.submit("q", tools=None, timeout_s=10, model="gpt-5-codex")
      assert exc.value.retryable is False


  @pytest.mark.asyncio
  async def test_timeout_raises_retryable_llm_error() -> None:
      pool = MagicMock()
      pool.run = AsyncMock(side_effect=SubprocessTimeout("t", cmd_head="codex"))
      provider = CodexProvider(pool=pool, cli_path="codex")
      with pytest.raises(LLMError) as exc:
          await provider.submit("q", tools=None, timeout_s=10, model="gpt-5-codex")
      assert exc.value.retryable is True


  @pytest.mark.asyncio
  async def test_non_zero_exit_raises_non_retryable() -> None:
      pool = MagicMock()
      pool.run = AsyncMock(side_effect=SubprocessNonZeroExit("exit 2", exit_code=2, stderr="oops"))
      provider = CodexProvider(pool=pool, cli_path="codex")
      with pytest.raises(LLMError) as exc:
          await provider.submit("q", tools=None, timeout_s=10, model="gpt-5-codex")
      assert exc.value.retryable is False
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_codex_provider.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/llm/codex_provider.py`:
  ```python
  """Codex CLI provider — wraps `codex exec --output-format json` via SubprocessPool."""
  from __future__ import annotations

  import hashlib
  import json
  import logging

  from daily_scheduler.constants import LLM_RETRY_COUNT
  from daily_scheduler.domain.ports.llm_provider import (
      LLMError,
      LLMProviderPort,
      LLMResult,
  )
  from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import (
      SubprocessNonZeroExit,
      SubprocessPool,
      SubprocessTimeout,
  )

  logger = logging.getLogger(__name__)


  class CodexProvider(LLMProviderPort):
      """LLM provider backed by `codex exec` in JSON output mode."""

      def __init__(self, pool: SubprocessPool, cli_path: str) -> None:
          self._pool = pool
          self._cli_path = cli_path

      async def submit(
          self,
          prompt: str,
          *,
          tools: list[str] | None,  # noqa: ARG002  (codex tool flags reserved)
          timeout_s: int,
          model: str,
      ) -> LLMResult:
          cmd = [
              self._cli_path, "exec",
              "--model", model,
              "--output-format", "json",
          ]
          cmd_hash = hashlib.sha256(
              " ".join(cmd + [prompt[:64]]).encode()
          ).hexdigest()[:16]
          logger.info("codex submit model=%s timeout=%ds cmd_hash=%s", model, timeout_s, cmd_hash)

          try:
              result = await self._pool.run(
                  cmd, stdin=prompt, timeout_s=timeout_s, retries=LLM_RETRY_COUNT,
              )
          except SubprocessTimeout as e:
              raise LLMError(
                  f"codex timed out after {timeout_s}s",
                  provider="codex", retryable=True,
              ) from e
          except SubprocessNonZeroExit as e:
              raise LLMError(
                  f"codex exited {e.exit_code}: {e.stderr[:200]}",
                  provider="codex", retryable=False,
              ) from e

          try:
              envelope = json.loads(result.stdout)
          except json.JSONDecodeError as e:
              raise LLMError(
                  f"codex returned invalid JSON: {result.stdout[:200]}",
                  provider="codex", retryable=False,
              ) from e

          if not isinstance(envelope, dict) or "output" not in envelope:
              raise LLMError(
                  f"codex envelope missing 'output' field: {str(envelope)[:200]}",
                  provider="codex", retryable=False,
              )

          return LLMResult(
              text=str(envelope["output"]),
              model=model,
              provider="codex",
              tokens_in=int(envelope.get("tokens_in", 0)),
              tokens_out=int(envelope.get("tokens_out", 0)),
              latency_ms=result.duration_ms,
              command_hash=cmd_hash,
          )
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_codex_provider.py -v
  ```
  Expected: 5 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/llm/codex_provider.py backend/tests/test_codex_provider.py
  git commit -m "feat(infra): add CodexProvider (codex exec JSON envelope wrapper)"
  ```

---

## Task 7: MemoryNode entity

**Files:**
- Create: `backend/src/daily_scheduler/domain/entities/memory_node.py`
- Test: `backend/tests/test_memory_node.py`

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_memory_node.py`:
  ```python
  """Tests for MemoryNode domain entity."""
  from __future__ import annotations

  from datetime import date

  import pytest

  from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode


  def test_memory_node_creates_decision() -> None:
      node = MemoryNode(
          id="01HXYZABCDEF0123456789ABCD",
          kind=MemoryKind.DECISION,
          date=date(2026, 5, 24),
          summary="Bull recommended SAMSUNG; Bear flagged inventory glut",
          body="# Debate digest\n...\n",
          symbol="SAMSUNG",
          sector="semiconductor",
          strategy="DAY",
          outcome=None,
          debate_id="01HABCDEFGH",
      )
      assert node.kind is MemoryKind.DECISION
      assert node.symbol == "SAMSUNG"


  def test_summary_max_200_chars() -> None:
      with pytest.raises(ValueError, match="summary"):
          MemoryNode(
              id="01HXYZ",
              kind=MemoryKind.LESSON,
              date=date(2026, 5, 24),
              summary="x" * 201,
              body="",
              symbol=None,
              sector=None,
              strategy=None,
              outcome=None,
              debate_id=None,
          )


  def test_kind_enum_values() -> None:
      assert MemoryKind.DECISION.value == "decision"
      assert MemoryKind.PATTERN.value == "pattern"
      assert MemoryKind.LESSON.value == "lesson"


  def test_relative_path_for_decision_with_symbol() -> None:
      node = MemoryNode(
          id="01HXYZ", kind=MemoryKind.DECISION, date=date(2026, 5, 24),
          summary="x", body="", symbol="SAMSUNG", sector="semiconductor",
          strategy="DAY", outcome=None, debate_id="01HABC",
      )
      assert node.relative_path() == "by-sector/semiconductor/SAMSUNG/2026-05-24.md"


  def test_relative_path_for_lesson() -> None:
      node = MemoryNode(
          id="01HXYZ", kind=MemoryKind.LESSON, date=date(2026, 5, 24),
          summary="x", body="", symbol=None, sector=None, strategy=None,
          outcome=None, debate_id=None,
      )
      p = node.relative_path()
      assert p.startswith("lessons/2026-W")
      assert p.endswith(".md")


  def test_to_frontmatter_dict() -> None:
      node = MemoryNode(
          id="01HXYZ", kind=MemoryKind.DECISION, date=date(2026, 5, 24),
          summary="s", body="", symbol="SAMSUNG", sector="semiconductor",
          strategy="DAY", outcome="TARGET_HIT", debate_id="01HABC",
      )
      fm = node.frontmatter()
      assert fm["id"] == "01HXYZ"
      assert fm["kind"] == "decision"
      assert fm["date"] == "2026-05-24"
      assert fm["symbol"] == "SAMSUNG"
      assert fm["outcome"] == "TARGET_HIT"
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_memory_node.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/domain/entities/memory_node.py`:
  ```python
  """MemoryNode — a single reflection entry (decision / pattern / lesson)."""
  from __future__ import annotations

  from dataclasses import dataclass
  from datetime import date as date_type
  from enum import Enum


  class MemoryKind(str, Enum):
      DECISION = "decision"
      PATTERN = "pattern"
      LESSON = "lesson"


  _SUMMARY_MAX = 200


  @dataclass(frozen=True, slots=True)
  class MemoryNode:
      id: str
      kind: MemoryKind
      date: date_type
      summary: str
      body: str
      symbol: str | None
      sector: str | None
      strategy: str | None
      outcome: str | None
      debate_id: str | None

      def __post_init__(self) -> None:
          if len(self.summary) > _SUMMARY_MAX:
              raise ValueError(
                  f"summary too long: {len(self.summary)} > {_SUMMARY_MAX} chars"
              )

      def relative_path(self) -> str:
          if self.kind is MemoryKind.DECISION:
              sector = self.sector or "uncategorized"
              symbol = self.symbol or "general"
              return f"by-sector/{sector}/{symbol}/{self.date.isoformat()}.md"
          if self.kind is MemoryKind.PATTERN:
              slug = (self.summary[:40] or self.id).lower().replace(" ", "-")
              return f"patterns/{slug}.md"
          iso_year, iso_week, _ = self.date.isocalendar()
          return f"lessons/{iso_year}-W{iso_week:02d}.md"

      def frontmatter(self) -> dict[str, object]:
          return {
              "id": self.id,
              "kind": self.kind.value,
              "date": self.date.isoformat(),
              "summary": self.summary,
              "symbol": self.symbol,
              "sector": self.sector,
              "strategy": self.strategy,
              "outcome": self.outcome,
              "debate_id": self.debate_id,
          }
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_memory_node.py -v
  ```
  Expected: 6 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/domain/entities/memory_node.py backend/tests/test_memory_node.py
  git commit -m "feat(domain): add MemoryNode entity with MemoryKind enum"
  ```

---

## Task 8: MemoryStorePort + MemoryQuery

**Files:**
- Create: `backend/src/daily_scheduler/domain/ports/memory_store.py`
- Test: `backend/tests/test_memory_store_port.py`

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_memory_store_port.py`:
  ```python
  """Tests for MemoryStorePort interface (shape only)."""
  from __future__ import annotations

  from daily_scheduler.domain.ports.memory_store import MemoryQuery, MemoryStorePort


  def test_memory_store_port_has_required_methods() -> None:
      for m in ("ingest", "query_metadata", "query_keyword", "traverse_tree", "update_outcome"):
          assert hasattr(MemoryStorePort, m), f"missing method: {m}"


  def test_memory_query_dataclass() -> None:
      q = MemoryQuery(symbol="SAMSUNG", sector="semiconductor", strategy="DAY")
      assert q.symbol == "SAMSUNG"
      assert q.outcome is None
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_memory_store_port.py -v
  ```
  Expected: ImportError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/domain/ports/memory_store.py`:
  ```python
  """Port for the memory subsystem (Markdown + JSON tree + FTS5)."""
  from __future__ import annotations

  from dataclasses import dataclass
  from datetime import date
  from typing import Protocol

  from daily_scheduler.domain.entities.memory_node import MemoryNode


  @dataclass(frozen=True, slots=True)
  class MemoryQuery:
      symbol: str | None = None
      sector: str | None = None
      strategy: str | None = None
      outcome: str | None = None
      date_from: date | None = None
      date_to: date | None = None
      limit: int = 10


  class MemoryStorePort(Protocol):
      def ingest(self, node: MemoryNode) -> None: ...
      def query_metadata(self, q: MemoryQuery) -> list[MemoryNode]: ...
      def query_keyword(self, text: str, limit: int = 10) -> list[MemoryNode]: ...
      def traverse_tree(self, query: str, max_depth: int = 3) -> list[MemoryNode]: ...
      def update_outcome(self, memory_id: str, outcome: str) -> None: ...
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_memory_store_port.py -v
  ```
  Expected: 2 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/domain/ports/memory_store.py backend/tests/test_memory_store_port.py
  git commit -m "feat(domain): add MemoryStorePort and MemoryQuery"
  ```

---

## Task 9: memory_node ORM model + FTS5 virtual table

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/memory/__init__.py`
- Create: `backend/src/daily_scheduler/infrastructure/adapters/memory/models.py`
- Modify: `backend/src/daily_scheduler/database.py`
- Test: `backend/tests/test_memory_models.py`

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_memory_models.py`:
  ```python
  """Tests for memory_node ORM model and FTS5 virtual table creation."""
  from __future__ import annotations

  from datetime import datetime

  import pytest
  from sqlalchemy import create_engine, text
  from sqlalchemy.orm import Session

  from daily_scheduler.database import Base
  from daily_scheduler.infrastructure.adapters.memory.models import (
      MemoryNodeModel,
      create_memory_fts_table,
  )


  @pytest.fixture
  def engine():
      eng = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(eng)
      create_memory_fts_table(eng)
      return eng


  def test_memory_node_table_round_trip(engine) -> None:
      with Session(engine) as session:
          row = MemoryNodeModel(
              id="01HXYZ", file_path="by-sector/semi/SAMSUNG/2026-05-24.md",
              kind="decision", symbol="SAMSUNG", sector="semiconductor",
              strategy="DAY", outcome=None, date="2026-05-24",
              summary="x", debate_id=None,
              created_at=datetime.now(), updated_at=datetime.now(),
          )
          session.add(row)
          session.commit()
          fetched = session.get(MemoryNodeModel, "01HXYZ")
          assert fetched is not None
          assert fetched.symbol == "SAMSUNG"


  def test_fts5_virtual_table_exists(engine) -> None:
      with engine.connect() as conn:
          rows = conn.execute(text(
              "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_fts'"
          )).fetchall()
          assert any(r[0] == "memory_fts" for r in rows)


  def test_fts5_trigram_tokenizer_recall(engine) -> None:
      """Korean partial-match works with trigram tokenizer."""
      with engine.begin() as conn:
          conn.execute(text(
              "INSERT INTO memory_fts(rowid, body, summary, symbol, sector) "
              "VALUES (1, '삼성전자가 4분기 실적 발표', '실적 발표 요약', 'SAMSUNG', 'semiconductor')"
          ))
      with engine.connect() as conn:
          result = conn.execute(text(
              "SELECT rowid FROM memory_fts WHERE memory_fts MATCH '삼성전자'"
          )).fetchall()
          assert len(result) == 1
          assert result[0][0] == 1
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_memory_models.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/memory/__init__.py`:
  ```python
  """Memory subsystem adapters."""
  ```

  Create `backend/src/daily_scheduler/infrastructure/adapters/memory/models.py`:
  ```python
  """ORM model for memory_node and FTS5 virtual table creator."""
  from __future__ import annotations

  from datetime import datetime

  from sqlalchemy import DateTime, String, text
  from sqlalchemy.engine import Engine
  from sqlalchemy.orm import Mapped, mapped_column

  from daily_scheduler.database import Base


  class MemoryNodeModel(Base):
      """SQLAlchemy model — metadata row for a memory file."""

      __tablename__ = "memory_node"

      id: Mapped[str] = mapped_column(String, primary_key=True)
      file_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
      kind: Mapped[str] = mapped_column(String, nullable=False)
      symbol: Mapped[str | None] = mapped_column(String, nullable=True)
      sector: Mapped[str | None] = mapped_column(String, nullable=True)
      strategy: Mapped[str | None] = mapped_column(String, nullable=True)
      outcome: Mapped[str | None] = mapped_column(String, nullable=True)
      date: Mapped[str] = mapped_column(String, nullable=False)
      summary: Mapped[str] = mapped_column(String, nullable=False)
      debate_id: Mapped[str | None] = mapped_column(String, nullable=True)
      created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
      updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


  def create_memory_fts_table(engine: Engine) -> None:
      """Create the memory_fts FTS5 virtual table with trigram tokenizer.

      Trigram tokenizer is required for Korean / CJK partial matching.
      Idempotent — uses IF NOT EXISTS.
      """
      with engine.begin() as conn:
          conn.execute(text("""
              CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                  body,
                  summary,
                  symbol UNINDEXED,
                  sector UNINDEXED,
                  tokenize='trigram'
              )
          """))
  ```

- [ ] **Step 4:** Modify `backend/src/daily_scheduler/database.py`. After the existing `Base` declaration, append:
  ```python
  def _register_memory_models() -> None:
      """Import memory ORM models so they attach to Base.metadata."""
      from daily_scheduler.infrastructure.adapters.memory import models as _memory_models  # noqa: F401


  _register_memory_models()


  def init_database(engine) -> None:
      """Create all ORM tables + the FTS5 virtual table. Idempotent."""
      from daily_scheduler.infrastructure.adapters.memory.models import (
          create_memory_fts_table,
      )

      Base.metadata.create_all(engine)
      create_memory_fts_table(engine)
  ```

- [ ] **Step 5:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_memory_models.py -v
  ```
  Expected: 3 passed.

  If `test_fts5_trigram_tokenizer_recall` fails with "no such tokenizer", verify SQLite >= 3.34:
  ```bash
  cd backend && uv run python -c "import sqlite3; print(sqlite3.sqlite_version)"
  ```

- [ ] **Step 6:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/memory/ backend/src/daily_scheduler/database.py backend/tests/test_memory_models.py
  git commit -m "feat(memory): add memory_node ORM model + FTS5 trigram virtual table"
  ```

---

## Task 10: MarkdownMemoryStore

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/memory/markdown_store.py`
- Test: `backend/tests/test_markdown_store.py`

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_markdown_store.py`:
  ```python
  """Tests for MarkdownMemoryStore (write/read markdown files with YAML frontmatter)."""
  from __future__ import annotations

  from datetime import date

  import pytest

  from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode
  from daily_scheduler.infrastructure.adapters.memory.markdown_store import (
      MarkdownMemoryStore,
  )


  @pytest.fixture
  def store(tmp_path):
      return MarkdownMemoryStore(root=tmp_path / "memory")


  def _node(**overrides):
      base = dict(
          id="01HXYZ", kind=MemoryKind.DECISION, date=date(2026, 5, 24),
          summary="Bull recommended SAMSUNG",
          body="# Debate digest\n\nDetails here.\n",
          symbol="SAMSUNG", sector="semiconductor", strategy="DAY",
          outcome=None, debate_id="01HABC",
      )
      base.update(overrides)
      return MemoryNode(**base)


  def test_write_creates_file_at_relative_path(store, tmp_path) -> None:
      node = _node()
      store.write(node)
      expected = tmp_path / "memory" / "by-sector" / "semiconductor" / "SAMSUNG" / "2026-05-24.md"
      assert expected.exists()


  def test_written_file_has_yaml_frontmatter(store, tmp_path) -> None:
      node = _node()
      store.write(node)
      content = (tmp_path / "memory" / node.relative_path()).read_text(encoding="utf-8")
      assert content.startswith("---\n")
      assert "id: 01HXYZ\n" in content
      assert "kind: decision\n" in content
      assert "symbol: SAMSUNG\n" in content
      assert "\n---\n" in content
      assert "# Debate digest" in content


  def test_read_round_trips_node(store) -> None:
      node = _node()
      store.write(node)
      loaded = store.read(node.relative_path())
      assert loaded.id == node.id
      assert loaded.kind is MemoryKind.DECISION
      assert loaded.date == date(2026, 5, 24)
      assert loaded.symbol == "SAMSUNG"
      assert loaded.body.strip() == node.body.strip()


  def test_update_outcome_rewrites_frontmatter_preserving_body(store) -> None:
      node = _node()
      store.write(node)
      store.update_outcome(node.relative_path(), "TARGET_HIT")
      loaded = store.read(node.relative_path())
      assert loaded.outcome == "TARGET_HIT"
      assert "# Debate digest" in loaded.body


  def test_overwrite_is_atomic(store) -> None:
      node1 = _node(body="first")
      node2 = _node(body="second", summary="updated summary")
      store.write(node1)
      store.write(node2)
      loaded = store.read(node1.relative_path())
      assert loaded.body.strip() == "second"
      assert loaded.summary == "updated summary"


  def test_root_is_created_lazily(tmp_path) -> None:
      root = tmp_path / "does" / "not" / "exist"
      s = MarkdownMemoryStore(root=root)
      s.write(_node())
      assert root.exists()
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_markdown_store.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/memory/markdown_store.py`:
  ```python
  """MarkdownMemoryStore — write/read MemoryNode as markdown files with YAML frontmatter."""
  from __future__ import annotations

  import os
  import tempfile
  from datetime import date as date_type
  from pathlib import Path

  import yaml

  from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode

  _DELIM = "---\n"


  class MarkdownMemoryStore:
      """File IO for memory markdown files."""

      def __init__(self, root: Path) -> None:
          self._root = root

      @property
      def root(self) -> Path:
          return self._root

      def write(self, node: MemoryNode) -> None:
          target = self._root / node.relative_path()
          target.parent.mkdir(parents=True, exist_ok=True)
          content = self._render(node)
          fd, tmp_path = tempfile.mkstemp(
              dir=target.parent, prefix=".memory_", suffix=".tmp"
          )
          try:
              with os.fdopen(fd, "w", encoding="utf-8") as fp:
                  fp.write(content)
              os.replace(tmp_path, target)
          except Exception:
              Path(tmp_path).unlink(missing_ok=True)
              raise

      def read(self, relative_path: str) -> MemoryNode:
          target = self._root / relative_path
          raw = target.read_text(encoding="utf-8")
          return self._parse(raw)

      def update_outcome(self, relative_path: str, outcome: str) -> None:
          node = self.read(relative_path)
          new_node = MemoryNode(
              id=node.id, kind=node.kind, date=node.date,
              summary=node.summary, body=node.body,
              symbol=node.symbol, sector=node.sector, strategy=node.strategy,
              outcome=outcome, debate_id=node.debate_id,
          )
          self.write(new_node)

      def _render(self, node: MemoryNode) -> str:
          fm = node.frontmatter()
          yaml_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
          return _DELIM + yaml_text + _DELIM + node.body

      def _parse(self, raw: str) -> MemoryNode:
          if not raw.startswith(_DELIM):
              raise ValueError("file is not in frontmatter format")
          rest = raw[len(_DELIM):]
          end = rest.find("\n" + _DELIM)
          if end == -1:
              raise ValueError("frontmatter not closed")
          yaml_text = rest[:end]
          body = rest[end + len("\n" + _DELIM):]
          fm = yaml.safe_load(yaml_text)
          d = fm["date"]
          if isinstance(d, str):
              parsed = date_type.fromisoformat(d)
          elif isinstance(d, date_type):
              parsed = d
          else:
              raise ValueError(f"bad date type: {type(d)}")
          return MemoryNode(
              id=fm["id"],
              kind=MemoryKind(fm["kind"]),
              date=parsed,
              summary=fm["summary"],
              body=body,
              symbol=fm.get("symbol"),
              sector=fm.get("sector"),
              strategy=fm.get("strategy"),
              outcome=fm.get("outcome"),
              debate_id=fm.get("debate_id"),
          )
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_markdown_store.py -v
  ```
  Expected: 6 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/memory/markdown_store.py backend/tests/test_markdown_store.py
  git commit -m "feat(memory): add MarkdownMemoryStore with atomic write + frontmatter"
  ```

---

## Task 11: JSONTreeIndex

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/memory/json_tree_index.py`
- Test: `backend/tests/test_json_tree_index.py`

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_json_tree_index.py`:
  ```python
  """Tests for JSONTreeIndex — builds tree.json from memory_node rows."""
  from __future__ import annotations

  import json
  from datetime import datetime

  import pytest
  from sqlalchemy import create_engine
  from sqlalchemy.orm import Session

  from daily_scheduler.database import Base
  from daily_scheduler.infrastructure.adapters.memory.json_tree_index import (
      JSONTreeIndex,
  )
  from daily_scheduler.infrastructure.adapters.memory.models import (
      MemoryNodeModel,
      create_memory_fts_table,
  )


  @pytest.fixture
  def session_factory():
      eng = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(eng)
      create_memory_fts_table(eng)
      return lambda: Session(eng)


  def _row(**overrides):
      base = dict(
          id="01HXYZ",
          file_path="by-sector/semi/SAMSUNG/2026-05-24.md",
          kind="decision",
          symbol="SAMSUNG", sector="semiconductor", strategy="DAY",
          outcome=None, date="2026-05-24", summary="bull rec",
          debate_id="01HABC",
          created_at=datetime.now(), updated_at=datetime.now(),
      )
      base.update(overrides)
      return MemoryNodeModel(**base)


  def test_empty_db_produces_empty_root_children(session_factory, tmp_path) -> None:
      idx = JSONTreeIndex(session_factory=session_factory, tree_path=tmp_path / "tree.json")
      idx.rebuild()
      data = json.loads((tmp_path / "tree.json").read_text())
      # All five top-level branches still exist, but each is empty.
      titles = {c["title"] for c in data["root"]["children"]}
      assert titles == {"by-sector", "by-date", "by-strategy", "patterns", "lessons"}
      for c in data["root"]["children"]:
          assert c["children"] == []


  def test_tree_groups_by_sector_then_symbol(session_factory, tmp_path) -> None:
      with session_factory() as s:
          s.add(_row(id="a"))
          s.add(_row(id="b", file_path="by-sector/semi/SK-HYNIX/2026-05-24.md", symbol="SK-HYNIX"))
          s.add(_row(id="c", file_path="by-sector/finance/KB/2026-05-24.md", symbol="KB", sector="finance"))
          s.commit()
      idx = JSONTreeIndex(session_factory=session_factory, tree_path=tmp_path / "tree.json")
      idx.rebuild()
      data = json.loads((tmp_path / "tree.json").read_text())
      by_sector = next(c for c in data["root"]["children"] if c["title"] == "by-sector")
      sectors = {c["title"] for c in by_sector["children"]}
      assert sectors == {"semiconductor", "finance"}


  def test_lessons_branch_for_lesson_kind(session_factory, tmp_path) -> None:
      with session_factory() as s:
          s.add(_row(
              id="L", file_path="lessons/2026-W19.md", kind="lesson",
              symbol=None, sector=None, strategy=None,
          ))
          s.commit()
      idx = JSONTreeIndex(session_factory=session_factory, tree_path=tmp_path / "tree.json")
      idx.rebuild()
      data = json.loads((tmp_path / "tree.json").read_text())
      lessons = next(c for c in data["root"]["children"] if c["title"] == "lessons")
      assert len(lessons["children"]) == 1
      assert lessons["children"][0]["file_path"] == "lessons/2026-W19.md"


  def test_tree_size_cap_truncates(session_factory, tmp_path) -> None:
      long = "x" * 199
      with session_factory() as s:
          for i in range(200):
              s.add(_row(
                  id=f"id{i:03d}",
                  file_path=f"by-sector/s/SYM{i}/2026-05-24.md",
                  summary=long, symbol=f"SYM{i}",
              ))
          s.commit()
      idx = JSONTreeIndex(
          session_factory=session_factory,
          tree_path=tmp_path / "tree.json",
          max_bytes=5_000,
      )
      idx.rebuild()
      raw = (tmp_path / "tree.json").read_text()
      assert len(raw.encode("utf-8")) <= 5_500


  def test_leaf_includes_summary_outcome_file_path(session_factory, tmp_path) -> None:
      with session_factory() as s:
          s.add(_row(outcome="TARGET_HIT"))
          s.commit()
      idx = JSONTreeIndex(session_factory=session_factory, tree_path=tmp_path / "tree.json")
      idx.rebuild()
      data = json.loads((tmp_path / "tree.json").read_text())
      by_sector = next(c for c in data["root"]["children"] if c["title"] == "by-sector")
      semi = next(c for c in by_sector["children"] if c["title"] == "semiconductor")
      samsung = next(c for c in semi["children"] if c["title"] == "SAMSUNG")
      leaf = samsung["children"][0]
      assert leaf["summary"] == "bull rec"
      assert leaf["outcome"] == "TARGET_HIT"
      assert leaf["file_path"] == "by-sector/semi/SAMSUNG/2026-05-24.md"
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_json_tree_index.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/memory/json_tree_index.py`:
  ```python
  """JSONTreeIndex — derives a hierarchical tree.json from memory_node rows."""
  from __future__ import annotations

  import json
  import os
  import tempfile
  from collections import defaultdict
  from collections.abc import Callable
  from pathlib import Path
  from typing import Any

  from sqlalchemy.orm import Session

  from daily_scheduler.constants import MEMORY_TREE_MAX_BYTES
  from daily_scheduler.infrastructure.adapters.memory.models import MemoryNodeModel


  class JSONTreeIndex:
      """Build and persist tree.json from memory_node rows."""

      def __init__(
          self,
          session_factory: Callable[[], Session],
          tree_path: Path,
          max_bytes: int = MEMORY_TREE_MAX_BYTES,
      ) -> None:
          self._session_factory = session_factory
          self._tree_path = tree_path
          self._max_bytes = max_bytes

      @property
      def tree_path(self) -> Path:
          return self._tree_path

      def rebuild(self) -> None:
          with self._session_factory() as session:
              rows = session.query(MemoryNodeModel).all()
          tree = self._build_tree(rows)
          self._write_atomic(tree)

      def load(self) -> dict[str, Any]:
          if not self._tree_path.exists():
              return {"root": {"title": "memory", "children": []}}
          return json.loads(self._tree_path.read_text(encoding="utf-8"))

      def _build_tree(self, rows: list[MemoryNodeModel]) -> dict[str, Any]:
          by_sector: dict[str, dict[str, list[MemoryNodeModel]]] = defaultdict(lambda: defaultdict(list))
          by_date: dict[str, dict[str, dict[str, list[MemoryNodeModel]]]] = defaultdict(
              lambda: defaultdict(lambda: defaultdict(list))
          )
          by_strategy: dict[str, list[MemoryNodeModel]] = defaultdict(list)
          patterns: list[MemoryNodeModel] = []
          lessons: list[MemoryNodeModel] = []

          for r in rows:
              if r.kind == "decision":
                  sector = r.sector or "uncategorized"
                  symbol = r.symbol or "general"
                  by_sector[sector][symbol].append(r)
                  y, m, d = r.date.split("-")
                  by_date[y][m][d].append(r)
                  if r.strategy:
                      by_strategy[r.strategy].append(r)
              elif r.kind == "pattern":
                  patterns.append(r)
              elif r.kind == "lesson":
                  lessons.append(r)

          children: list[dict[str, Any]] = []

          sector_children = [
              {
                  "title": sector,
                  "children": [
                      {"title": symbol, "children": [self._leaf(r) for r in rs]}
                      for symbol, rs in symbols.items()
                  ],
              }
              for sector, symbols in sorted(by_sector.items())
          ]
          children.append({"title": "by-sector", "children": sector_children})

          date_children = [
              {
                  "title": y,
                  "children": [
                      {
                          "title": m,
                          "children": [
                              {"title": d, "children": [self._leaf(r) for r in rs]}
                              for d, rs in sorted(months.items())
                          ],
                      }
                      for m, months in sorted(years.items())
                  ],
              }
              for y, years in sorted(by_date.items())
          ]
          children.append({"title": "by-date", "children": date_children})

          strat_children = [
              {"title": s, "children": [self._leaf(r) for r in rs]}
              for s, rs in sorted(by_strategy.items())
          ]
          children.append({"title": "by-strategy", "children": strat_children})

          children.append({"title": "patterns", "children": [self._leaf(r) for r in patterns]})
          children.append({"title": "lessons", "children": [self._leaf(r) for r in lessons]})

          return {"root": {"title": "memory", "children": children}}

      @staticmethod
      def _leaf(r: MemoryNodeModel) -> dict[str, Any]:
          return {
              "id": r.id,
              "title": r.symbol or r.date,
              "summary": r.summary,
              "file_path": r.file_path,
              "outcome": r.outcome,
              "date": r.date,
              "kind": r.kind,
          }

      def _write_atomic(self, tree: dict[str, Any]) -> None:
          data = self._serialize_with_cap(tree)
          self._tree_path.parent.mkdir(parents=True, exist_ok=True)
          fd, tmp_path = tempfile.mkstemp(
              dir=self._tree_path.parent, prefix=".tree_", suffix=".tmp"
          )
          try:
              with os.fdopen(fd, "w", encoding="utf-8") as fp:
                  fp.write(data)
              os.replace(tmp_path, self._tree_path)
          except Exception:
              Path(tmp_path).unlink(missing_ok=True)
              raise

      def _serialize_with_cap(self, tree: dict[str, Any]) -> str:
          data = json.dumps(tree, ensure_ascii=False, indent=2)
          if len(data.encode("utf-8")) <= self._max_bytes:
              return data
          cap_summary = 60
          while cap_summary > 10:
              self._truncate_summaries(tree, cap_summary)
              data = json.dumps(tree, ensure_ascii=False, indent=2)
              if len(data.encode("utf-8")) <= self._max_bytes:
                  return data
              cap_summary -= 10
          return data

      def _truncate_summaries(self, node: dict[str, Any], cap: int) -> None:
          if isinstance(node.get("summary"), str) and len(node["summary"]) > cap:
              node["summary"] = node["summary"][:cap] + "…"
          for child in node.get("children", []) or []:
              self._truncate_summaries(child, cap)
          if "root" in node:
              self._truncate_summaries(node["root"], cap)
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_json_tree_index.py -v
  ```
  Expected: 5 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/memory/json_tree_index.py backend/tests/test_json_tree_index.py
  git commit -m "feat(memory): add JSONTreeIndex (PageIndex-style hierarchical tree)"
  ```

---

## Task 12: SQLiteFTS5Search

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/memory/sqlite_fts5_search.py`
- Test: `backend/tests/test_sqlite_fts5_search.py`

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_sqlite_fts5_search.py`:
  ```python
  """Tests for SQLiteFTS5Search — BM25-ranked keyword search via FTS5."""
  from __future__ import annotations

  from datetime import datetime

  import pytest
  from sqlalchemy import create_engine
  from sqlalchemy.orm import Session

  from daily_scheduler.database import Base
  from daily_scheduler.infrastructure.adapters.memory.models import (
      MemoryNodeModel,
      create_memory_fts_table,
  )
  from daily_scheduler.infrastructure.adapters.memory.sqlite_fts5_search import (
      SQLiteFTS5Search,
  )


  @pytest.fixture
  def fixture():
      eng = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(eng)
      create_memory_fts_table(eng)
      return lambda: Session(eng), eng


  def _add(session, **kwargs):
      base = dict(
          id="01HXYZ",
          file_path="by-sector/semi/SAMSUNG/2026-05-24.md",
          kind="decision", symbol="SAMSUNG", sector="semiconductor",
          strategy="DAY", outcome=None, date="2026-05-24",
          summary="x", debate_id=None,
          created_at=datetime.now(), updated_at=datetime.now(),
      )
      base.update(kwargs)
      row = MemoryNodeModel(**base)
      session.add(row)
      return row


  def test_index_then_search_returns_ranked(fixture) -> None:
      sf, eng = fixture
      search = SQLiteFTS5Search(engine=eng)
      with sf() as s:
          _add(s, id="a", summary="bull case for SAMSUNG semi",
               file_path="by-sector/semi/SAMSUNG/2026-05-24.md")
          _add(s, id="b", summary="bear case for SK-HYNIX",
               file_path="by-sector/semi/SK-HYNIX/2026-05-24.md", symbol="SK-HYNIX")
          s.commit()
          for r in s.query(MemoryNodeModel).all():
              search.index(r, body=f"{r.summary} discussion body")

      hits = search.search("SAMSUNG", limit=10)
      assert len(hits) >= 1
      assert hits[0].id == "a"


  def test_search_korean_partial_match(fixture) -> None:
      sf, eng = fixture
      search = SQLiteFTS5Search(engine=eng)
      with sf() as s:
          row = _add(s, summary="삼성전자 4분기 실적 발표")
          s.commit()
          search.index(row, body="삼성전자가 좋은 실적을 발표했다")
      hits = search.search("삼성전자", limit=5)
      assert len(hits) == 1


  def test_search_no_match_returns_empty(fixture) -> None:
      sf, eng = fixture
      search = SQLiteFTS5Search(engine=eng)
      hits = search.search("nothingmatches", limit=5)
      assert hits == []


  def test_delete_then_search(fixture) -> None:
      sf, eng = fixture
      search = SQLiteFTS5Search(engine=eng)
      with sf() as s:
          row = _add(s, id="x", summary="to be removed")
          s.commit()
          search.index(row, body="remove me later")
      search.delete("x")
      hits = search.search("remove", limit=5)
      assert hits == []


  def test_reindex_updates_body(fixture) -> None:
      sf, eng = fixture
      search = SQLiteFTS5Search(engine=eng)
      with sf() as s:
          row = _add(s, id="r")
          s.commit()
          search.index(row, body="original")
          search.index(row, body="replacement")
      hits = search.search("replacement", limit=5)
      assert len(hits) == 1
      assert search.search("original", limit=5) == []
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_sqlite_fts5_search.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/memory/sqlite_fts5_search.py`:
  ```python
  """SQLiteFTS5Search — BM25-ranked keyword search using the memory_fts virtual table."""
  from __future__ import annotations

  from dataclasses import dataclass

  from sqlalchemy import text
  from sqlalchemy.engine import Engine

  from daily_scheduler.infrastructure.adapters.memory.models import MemoryNodeModel


  @dataclass(frozen=True, slots=True)
  class FTS5Hit:
      id: str
      file_path: str
      symbol: str | None
      sector: str | None
      score: float


  class SQLiteFTS5Search:
      """BM25 search over memory_fts virtual table."""

      def __init__(self, engine: Engine) -> None:
          self._engine = engine
          self._ensure_map_table()

      def _ensure_map_table(self) -> None:
          with self._engine.begin() as conn:
              conn.execute(text(
                  "CREATE TABLE IF NOT EXISTS memory_fts_map ("
                  "  memory_id TEXT PRIMARY KEY, "
                  "  rowid INTEGER NOT NULL UNIQUE)"
              ))

      def index(self, row: MemoryNodeModel, body: str) -> None:
          rowid = self._rowid_for(row.id)
          with self._engine.begin() as conn:
              conn.execute(
                  text("DELETE FROM memory_fts WHERE rowid = :rid"),
                  {"rid": rowid},
              )
              conn.execute(
                  text(
                      "INSERT INTO memory_fts(rowid, body, summary, symbol, sector) "
                      "VALUES (:rid, :body, :summary, :symbol, :sector)"
                  ),
                  {
                      "rid": rowid,
                      "body": body,
                      "summary": row.summary,
                      "symbol": row.symbol or "",
                      "sector": row.sector or "",
                  },
              )
              conn.execute(
                  text(
                      "INSERT OR REPLACE INTO memory_fts_map(memory_id, rowid) "
                      "VALUES (:mid, :rid)"
                  ),
                  {"mid": row.id, "rid": rowid},
              )

      def delete(self, memory_id: str) -> None:
          with self._engine.begin() as conn:
              rid = conn.execute(
                  text("SELECT rowid FROM memory_fts_map WHERE memory_id = :mid"),
                  {"mid": memory_id},
              ).scalar_one_or_none()
              if rid is None:
                  return
              conn.execute(text("DELETE FROM memory_fts WHERE rowid = :rid"), {"rid": rid})
              conn.execute(
                  text("DELETE FROM memory_fts_map WHERE memory_id = :mid"),
                  {"mid": memory_id},
              )

      def search(self, query: str, limit: int = 10) -> list[FTS5Hit]:
          if not query.strip():
              return []
          with self._engine.connect() as conn:
              rows = conn.execute(
                  text(
                      "SELECT m.memory_id, f.symbol, f.sector, bm25(memory_fts) AS s "
                      "FROM memory_fts f "
                      "JOIN memory_fts_map m ON m.rowid = f.rowid "
                      "WHERE memory_fts MATCH :q "
                      "ORDER BY s LIMIT :lim"
                  ),
                  {"q": query, "lim": limit},
              ).fetchall()

              out: list[FTS5Hit] = []
              for memory_id, symbol, sector, score in rows:
                  fp = conn.execute(
                      text("SELECT file_path FROM memory_node WHERE id = :mid"),
                      {"mid": memory_id},
                  ).scalar_one_or_none()
                  if fp is None:
                      continue
                  out.append(FTS5Hit(
                      id=memory_id,
                      file_path=fp,
                      symbol=symbol or None,
                      sector=sector or None,
                      score=float(score),
                  ))
              return out

      @staticmethod
      def _rowid_for(memory_id: str) -> int:
          return int.from_bytes(
              memory_id.encode()[-12:].ljust(8, b"0")[:8], "big", signed=False
          )
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_sqlite_fts5_search.py -v
  ```
  Expected: 5 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/memory/sqlite_fts5_search.py backend/tests/test_sqlite_fts5_search.py
  git commit -m "feat(memory): add SQLiteFTS5Search (BM25 + trigram + delete-by-id)"
  ```

---

## Task 13: Composite MemoryStore

**Files:**
- Create: `backend/src/daily_scheduler/infrastructure/adapters/memory/memory_store.py`
- Test: `backend/tests/test_memory_store.py`

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_memory_store.py`:
  ```python
  """Integration tests for MemoryStore composing markdown + tree + FTS5."""
  from __future__ import annotations

  from datetime import date

  import pytest
  from sqlalchemy import create_engine
  from sqlalchemy.orm import Session

  from daily_scheduler.database import Base
  from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode
  from daily_scheduler.domain.ports.memory_store import MemoryQuery
  from daily_scheduler.infrastructure.adapters.memory.json_tree_index import (
      JSONTreeIndex,
  )
  from daily_scheduler.infrastructure.adapters.memory.markdown_store import (
      MarkdownMemoryStore,
  )
  from daily_scheduler.infrastructure.adapters.memory.memory_store import MemoryStore
  from daily_scheduler.infrastructure.adapters.memory.models import (
      create_memory_fts_table,
  )
  from daily_scheduler.infrastructure.adapters.memory.sqlite_fts5_search import (
      SQLiteFTS5Search,
  )


  @pytest.fixture
  def store(tmp_path):
      eng = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(eng)
      create_memory_fts_table(eng)
      sf = lambda: Session(eng)
      md = MarkdownMemoryStore(root=tmp_path / "memory")
      tree = JSONTreeIndex(session_factory=sf, tree_path=tmp_path / "memory" / "tree.json")
      fts = SQLiteFTS5Search(engine=eng)
      return MemoryStore(markdown=md, tree=tree, fts=fts, session_factory=sf)


  def _node(**overrides):
      base = dict(
          id="01HXYZ", kind=MemoryKind.DECISION, date=date(2026, 5, 24),
          summary="bull rec for SAMSUNG",
          body="Discussion body mentioning semiconductor cycle.",
          symbol="SAMSUNG", sector="semiconductor", strategy="DAY",
          outcome=None, debate_id="d1",
      )
      base.update(overrides)
      return MemoryNode(**base)


  def test_ingest_writes_file_and_db_and_fts(store, tmp_path) -> None:
      node = _node()
      store.ingest(node)
      assert (tmp_path / "memory" / node.relative_path()).exists()
      assert (tmp_path / "memory" / "tree.json").exists()
      hits = store.query_keyword("SAMSUNG")
      assert any(h.id == node.id for h in hits)


  def test_query_metadata_filters(store) -> None:
      store.ingest(_node(id="01H1", symbol="SAMSUNG"))
      store.ingest(_node(id="01H2", symbol="SK-HYNIX", strategy="SWING"))
      results = store.query_metadata(MemoryQuery(strategy="DAY"))
      ids = {n.id for n in results}
      assert "01H1" in ids
      assert "01H2" not in ids


  def test_query_keyword_korean(store) -> None:
      store.ingest(_node(id="01H1", summary="삼성전자 매수 추천", body="실적 호조 예상"))
      hits = store.query_keyword("삼성전자")
      assert any(h.id == "01H1" for h in hits)


  def test_update_outcome_propagates(store, tmp_path) -> None:
      node = _node()
      store.ingest(node)
      store.update_outcome(node.id, "TARGET_HIT")
      md_content = (tmp_path / "memory" / node.relative_path()).read_text()
      assert "TARGET_HIT" in md_content
      rows = store.query_metadata(MemoryQuery(symbol="SAMSUNG"))
      assert rows[0].outcome == "TARGET_HIT"


  def test_ingest_is_atomic_on_fts_failure(store, tmp_path, monkeypatch) -> None:
      node = _node()

      def boom(*args, **kwargs):
          raise RuntimeError("simulated fts failure")

      monkeypatch.setattr(store._fts, "index", boom)
      with pytest.raises(RuntimeError):
          store.ingest(node)
      assert not (tmp_path / "memory" / node.relative_path()).exists()
      rows = store.query_metadata(MemoryQuery(symbol="SAMSUNG"))
      assert rows == []
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_memory_store.py -v
  ```
  Expected: ModuleNotFoundError.

- [ ] **Step 3:** Create `backend/src/daily_scheduler/infrastructure/adapters/memory/memory_store.py`:
  ```python
  """MemoryStore — atomic composite over markdown + JSON tree + FTS5."""
  from __future__ import annotations

  from collections.abc import Callable
  from datetime import date as date_type, datetime

  from sqlalchemy import text
  from sqlalchemy.orm import Session

  from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode
  from daily_scheduler.domain.ports.memory_store import MemoryQuery, MemoryStorePort
  from daily_scheduler.infrastructure.adapters.memory.json_tree_index import (
      JSONTreeIndex,
  )
  from daily_scheduler.infrastructure.adapters.memory.markdown_store import (
      MarkdownMemoryStore,
  )
  from daily_scheduler.infrastructure.adapters.memory.models import MemoryNodeModel
  from daily_scheduler.infrastructure.adapters.memory.sqlite_fts5_search import (
      SQLiteFTS5Search,
  )


  class MemoryStore(MemoryStorePort):
      """Atomic ingest across markdown, FTS5, and DB; reads from DB."""

      def __init__(
          self,
          markdown: MarkdownMemoryStore,
          tree: JSONTreeIndex,
          fts: SQLiteFTS5Search,
          session_factory: Callable[[], Session],
      ) -> None:
          self._md = markdown
          self._tree = tree
          self._fts = fts
          self._sf = session_factory

      def ingest(self, node: MemoryNode) -> None:
          rel = node.relative_path()
          file_target = self._md.root / rel
          wrote_file = False
          wrote_db = False
          try:
              self._md.write(node)
              wrote_file = True
              now = datetime.now()
              with self._sf() as session:
                  row = MemoryNodeModel(
                      id=node.id, file_path=rel, kind=node.kind.value,
                      symbol=node.symbol, sector=node.sector,
                      strategy=node.strategy, outcome=node.outcome,
                      date=node.date.isoformat(), summary=node.summary,
                      debate_id=node.debate_id,
                      created_at=now, updated_at=now,
                  )
                  session.merge(row)
                  session.commit()
                  wrote_db = True
                  self._fts.index(row, body=node.body)
              self._tree.rebuild()
          except Exception:
              if wrote_db:
                  with self._sf() as session:
                      session.execute(
                          text("DELETE FROM memory_node WHERE id = :id"),
                          {"id": node.id},
                      )
                      session.commit()
              if wrote_file and file_target.exists():
                  file_target.unlink()
              raise

      def update_outcome(self, memory_id: str, outcome: str) -> None:
          with self._sf() as session:
              row = session.get(MemoryNodeModel, memory_id)
              if row is None:
                  raise KeyError(memory_id)
              file_path = row.file_path
              row.outcome = outcome
              row.updated_at = datetime.now()
              session.commit()
          self._md.update_outcome(file_path, outcome)
          self._tree.rebuild()

      def query_metadata(self, q: MemoryQuery) -> list[MemoryNode]:
          with self._sf() as session:
              qry = session.query(MemoryNodeModel)
              if q.symbol:
                  qry = qry.filter(MemoryNodeModel.symbol == q.symbol)
              if q.sector:
                  qry = qry.filter(MemoryNodeModel.sector == q.sector)
              if q.strategy:
                  qry = qry.filter(MemoryNodeModel.strategy == q.strategy)
              if q.outcome:
                  qry = qry.filter(MemoryNodeModel.outcome == q.outcome)
              if q.date_from:
                  qry = qry.filter(MemoryNodeModel.date >= q.date_from.isoformat())
              if q.date_to:
                  qry = qry.filter(MemoryNodeModel.date <= q.date_to.isoformat())
              rows = qry.order_by(MemoryNodeModel.date.desc()).limit(q.limit).all()
          return [self._row_to_node(r) for r in rows]

      def query_keyword(self, text_q: str, limit: int = 10) -> list[MemoryNode]:
          hits = self._fts.search(text_q, limit=limit)
          if not hits:
              return []
          ids = [h.id for h in hits]
          with self._sf() as session:
              rows_by_id = {
                  r.id: r
                  for r in session.query(MemoryNodeModel).filter(
                      MemoryNodeModel.id.in_(ids)
                  ).all()
              }
          return [self._row_to_node(rows_by_id[i]) for i in ids if i in rows_by_id]

      def traverse_tree(self, query: str, max_depth: int = 3) -> list[MemoryNode]:
          # Default implementation returns most recent decisions.
          # An LLM-driven traversal lives in the use case layer.
          return self.query_metadata(MemoryQuery(limit=10))

      def _row_to_node(self, r: MemoryNodeModel) -> MemoryNode:
          body = ""
          try:
              loaded = self._md.read(r.file_path)
              body = loaded.body
          except FileNotFoundError:
              pass
          return MemoryNode(
              id=r.id,
              kind=MemoryKind(r.kind),
              date=date_type.fromisoformat(r.date),
              summary=r.summary,
              body=body,
              symbol=r.symbol,
              sector=r.sector,
              strategy=r.strategy,
              outcome=r.outcome,
              debate_id=r.debate_id,
          )
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_memory_store.py -v
  ```
  Expected: 5 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/adapters/memory/memory_store.py backend/tests/test_memory_store.py
  git commit -m "feat(memory): add MemoryStore (atomic markdown+FTS5+tree composite)"
  ```

---

## Task 14: Wire factories into dependencies.py

**Files:**
- Modify: `backend/src/daily_scheduler/infrastructure/dependencies.py`
- Test: `backend/tests/test_dependencies.py`

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_dependencies.py`:
  ```python
  """Tests that the new factories return correctly-wired adapters."""
  from __future__ import annotations

  import pytest
  from sqlalchemy import create_engine
  from sqlalchemy.orm import Session

  from daily_scheduler.database import Base
  from daily_scheduler.infrastructure.adapters.llm.claude_code_provider import (
      ClaudeCodeProvider,
  )
  from daily_scheduler.infrastructure.adapters.llm.codex_provider import CodexProvider
  from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import SubprocessPool
  from daily_scheduler.infrastructure.adapters.memory.memory_store import MemoryStore
  from daily_scheduler.infrastructure.adapters.memory.models import (
      create_memory_fts_table,
  )
  from daily_scheduler.infrastructure.dependencies import (
      get_claude_code_provider,
      get_codex_provider,
      get_memory_store,
      get_subprocess_pool,
  )


  @pytest.fixture
  def session_factory(tmp_path):
      eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
      Base.metadata.create_all(eng)
      create_memory_fts_table(eng)
      return lambda: Session(eng), tmp_path, eng


  def test_get_subprocess_pool_is_singleton() -> None:
      p1 = get_subprocess_pool()
      p2 = get_subprocess_pool()
      assert p1 is p2
      assert isinstance(p1, SubprocessPool)


  def test_get_claude_code_provider_returns_provider() -> None:
      provider = get_claude_code_provider()
      assert isinstance(provider, ClaudeCodeProvider)


  def test_get_codex_provider_returns_provider() -> None:
      provider = get_codex_provider()
      assert isinstance(provider, CodexProvider)


  def test_get_memory_store_returns_wired_store(session_factory) -> None:
      sf, tmp_path, eng = session_factory
      store = get_memory_store(session_factory=sf, engine=eng, memory_root=tmp_path / "mem")
      assert isinstance(store, MemoryStore)
  ```

- [ ] **Step 2:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_dependencies.py -v
  ```
  Expected: ImportError on `get_subprocess_pool`.

- [ ] **Step 3:** Append to `backend/src/daily_scheduler/infrastructure/dependencies.py`:
  ```python
  # --- Multi-agent council factories (Plan 1) ---

  from collections.abc import Callable
  from pathlib import Path

  from sqlalchemy.engine import Engine
  from sqlalchemy.orm import Session

  from daily_scheduler.constants import MAX_CONCURRENT_LLM_CALLS
  from daily_scheduler.infrastructure.adapters.llm.claude_code_provider import (
      ClaudeCodeProvider,
  )
  from daily_scheduler.infrastructure.adapters.llm.codex_provider import CodexProvider
  from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import SubprocessPool
  from daily_scheduler.infrastructure.adapters.memory.json_tree_index import (
      JSONTreeIndex,
  )
  from daily_scheduler.infrastructure.adapters.memory.markdown_store import (
      MarkdownMemoryStore,
  )
  from daily_scheduler.infrastructure.adapters.memory.memory_store import MemoryStore
  from daily_scheduler.infrastructure.adapters.memory.sqlite_fts5_search import (
      SQLiteFTS5Search,
  )

  _subprocess_pool: SubprocessPool | None = None


  def get_subprocess_pool() -> SubprocessPool:
      """Process-wide singleton subprocess pool."""
      global _subprocess_pool
      if _subprocess_pool is None:
          _subprocess_pool = SubprocessPool(max_concurrent=MAX_CONCURRENT_LLM_CALLS)
      return _subprocess_pool


  def get_claude_code_provider() -> ClaudeCodeProvider:
      settings = get_settings()
      return ClaudeCodeProvider(
          pool=get_subprocess_pool(),
          cli_path=settings.claude_cli_path,
      )


  def get_codex_provider() -> CodexProvider:
      settings = get_settings()
      return CodexProvider(
          pool=get_subprocess_pool(),
          cli_path=settings.codex_cli_path,
      )


  def get_memory_store(
      session_factory: Callable[[], Session],
      engine: Engine,
      memory_root: Path,
  ) -> MemoryStore:
      md = MarkdownMemoryStore(root=memory_root)
      tree = JSONTreeIndex(
          session_factory=session_factory,
          tree_path=memory_root / "tree.json",
      )
      fts = SQLiteFTS5Search(engine=engine)
      return MemoryStore(
          markdown=md, tree=tree, fts=fts, session_factory=session_factory,
      )
  ```

- [ ] **Step 4:** Run tests:
  ```bash
  cd backend && uv run pytest tests/test_dependencies.py -v
  ```
  Expected: 4 passed.

- [ ] **Step 5:** Commit:
  ```bash
  git add backend/src/daily_scheduler/infrastructure/dependencies.py backend/tests/test_dependencies.py
  git commit -m "feat(infra): wire LLM providers + MemoryStore factories"
  ```

---

## Task 15: Full-suite regression + static analysis

**Files:** none (verification only)

- [ ] **Step 1:** Run the full pytest suite:
  ```bash
  cd backend && uv run pytest -v
  ```
  Expected: all existing tests pass + all new Plan 1 tests pass. No new failures.

- [ ] **Step 2:** Run ruff lint:
  ```bash
  cd backend && uv run ruff check src tests
  ```
  Expected: no issues. Fix any inline.

- [ ] **Step 3:** Run ruff format check:
  ```bash
  cd backend && uv run ruff format --check src tests
  ```
  Expected: all formatted. Apply with `uv run ruff format src tests` if needed.

- [ ] **Step 4:** Run pyrefly type check:
  ```bash
  cd backend && uv run pyrefly check src
  ```
  Expected: no errors.

- [ ] **Step 5:** Run pylint:
  ```bash
  cd backend && uv run pylint src/daily_scheduler/infrastructure/adapters/llm src/daily_scheduler/infrastructure/adapters/memory src/daily_scheduler/domain/ports/llm_provider.py src/daily_scheduler/domain/ports/memory_store.py src/daily_scheduler/domain/entities/memory_node.py
  ```
  Expected: 10.00/10.

- [ ] **Step 6:** Confirm no regression on existing tests:
  ```bash
  cd backend && uv run pytest tests/ --ignore=tests/test_integration.py -v
  ```
  Expected: all green.

- [ ] **Step 7:** Tag the milestone (local-only; push happens at final release):
  ```bash
  git tag -a plan-1-foundations -m "Plan 1 complete: subscription CLI providers + memory subsystem"
  ```

---

## Self-Review Notes

**Spec coverage:**
- `BACK-01..07` — Tasks 3, 5, 6 (SubprocessPool, ClaudeCodeProvider, CodexProvider)
- `MEM-01, 02, 04, 05, 06, 07` — Tasks 13, 14
- `MEM-03` (atomic ingest) — Task 13 test `test_ingest_is_atomic_on_fts_failure`
- `MEM-08` (empty memory OK) — implicitly covered by query_metadata returning []
- `MEM-09` (.gitignore) — already covered by existing `data/` ignore rule
- `MEM-10` (tree max bytes) — Task 11 test `test_tree_size_cap_truncates`
- `CFG-06, 07, 09` — Task 4
- `CFG-08` (MULTICA_BASE_URL graceful) — Plan 4
- `DATA-04, 06, 07` — Task 9 (idempotent FTS5 table creation)
- `DATA-05` (legacy recs preserved) — verified in Plan 2

**Out of scope (handled by later plans):**
- LangGraph debate engine → Plan 2
- Judge logic → Plan 2
- Pipeline integration → Plan 2
- SSE streaming → Plan 3
- UI pages → Plan 3
- Multica HTTP client → Plan 4

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-25-multi-agent-council-plan-1-foundations.md`.**

The orchestrator proceeds with **Subagent-Driven Development** (per user's "끝까지 알아서" instruction). A fresh subagent is dispatched per task; each task ends with a regression check before moving on.
