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
