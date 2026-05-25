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
        except TimeoutError as e:
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
