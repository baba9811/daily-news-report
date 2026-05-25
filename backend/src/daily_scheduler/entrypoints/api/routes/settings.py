"""Settings router — view and update configuration."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import Any

from fastapi import APIRouter

from daily_scheduler.config import ENV_FILE, get_settings
from daily_scheduler.entrypoints.api.schemas.settings import (
    SettingsOut,
    SettingsUpdate,
    StatusOut,
    TestEmailResult,
    UpdateResult,
)
from daily_scheduler.infrastructure.dependencies import (
    get_email_sender,
)

# Alias the stdlib async subprocess spawner once, matching the pattern used by
# ``infrastructure/adapters/llm/subprocess_pool.py``. Aliasing keeps each call
# site to a single recognizable verb and avoids repeating the long module path.
_spawn = asyncio.create_subprocess_exec

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
)

SAFE_UPDATE_FIELDS: dict[str, str] = {
    "smtp_host": "SMTP_HOST",
    "smtp_port": "SMTP_PORT",
    "smtp_user": "SMTP_USER",
    "smtp_password": "SMTP_PASSWORD",
    "email_from": "EMAIL_FROM",
    "email_to": "EMAIL_TO",
    "claude_model": "CLAUDE_MODEL",
    "report_language": "REPORT_LANGUAGE",
}


@router.get("", response_model=SettingsOut)
def get_current_settings() -> SettingsOut:
    """Return current application settings."""
    s = get_settings()
    return SettingsOut(
        smtp_host=s.smtp_host,
        smtp_port=s.smtp_port,
        smtp_user=s.smtp_user,
        smtp_password_set=bool(
            s.smtp_password.get_secret_value(),
        ),
        email_from=s.email_from,
        email_to=s.email_to,
        claude_model=s.claude_model,
        report_language=s.report_language,
    )


@router.put("", response_model=UpdateResult)
def update_settings(update: SettingsUpdate) -> UpdateResult:
    """Update settings by writing to .env file.

    Only safe fields can be updated. Sensitive paths like
    claude_cli_path and database_url are not writable via API.
    """
    from dotenv import set_key

    env_path = str(ENV_FILE)
    updated_fields = []

    for field_name, env_key in SAFE_UPDATE_FIELDS.items():
        value = getattr(update, field_name)
        if value is not None:
            str_value = str(value) if not isinstance(value, list) else str(value)
            set_key(env_path, env_key, str_value)
            updated_fields.append(env_key)

    return UpdateResult(
        updated=updated_fields,
        message="Settings updated. Restart server to apply.",
    )


@router.post("/test-email", response_model=TestEmailResult)
def test_email() -> TestEmailResult:
    """Send a test email to verify SMTP config."""
    sender = get_email_sender()
    success = sender.send(
        "[Test] Daily Scheduler Email Test",
        "<h1>Email Test</h1><p>If you see this, your email configuration is working correctly!</p>",
    )
    return TestEmailResult(success=success)


@router.get("/status", response_model=StatusOut)
def health_check() -> StatusOut:
    """Check system health: DB, Claude CLI, SMTP."""
    settings = get_settings()

    db_ok = settings.db_path.exists()

    try:
        result = subprocess.run(
            [settings.claude_cli_path, "--version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        cli_ok = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        cli_ok = False

    smtp_ok = bool(settings.smtp_user and settings.smtp_password.get_secret_value())

    return StatusOut(
        database=db_ok,
        claude_cli=cli_ok,
        smtp_configured=smtp_ok,
        all_ok=db_ok and cli_ok and smtp_ok,
    )


async def _version_for(cli_path: str) -> str | None:
    """Best-effort `--version` probe for a CLI binary; never raises."""
    try:
        proc = await _spawn(
            cli_path,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=3)
        if not out:
            return None
        decoded = out.decode(errors="replace").strip()
        return decoded.splitlines()[0] if decoded else None
    except (OSError, TimeoutError):
        return None


@router.get("/health")
async def get_health() -> dict[str, Any]:
    """Report CLI (claude / codex) and Multica connectivity status.

    Always returns the same three top-level keys regardless of availability,
    so the frontend can render a consistent layout.
    """
    claude_path = shutil.which("claude")
    codex_path = shutil.which("codex")

    claude_version = await _version_for(claude_path) if claude_path else None
    codex_version = await _version_for(codex_path) if codex_path else None

    settings = get_settings()
    multica_up = False
    if settings.multica_base_url:
        # Imported lazily so the route can be unit-tested without httpx
        # being part of the import-time graph.
        from daily_scheduler.infrastructure.adapters.multica.http_client import (
            MulticaHTTPClient,
        )

        try:
            client = MulticaHTTPClient(base_url=settings.multica_base_url)
            multica_up = await client.health()
        except Exception:  # pylint: disable=broad-exception-caught
            multica_up = False

    return {
        "claude_cli": {
            "available": bool(claude_path),
            "path": claude_path,
            "version": claude_version,
        },
        "codex_cli": {
            "available": bool(codex_path),
            "path": codex_path,
            "version": codex_version,
        },
        "multica": {
            "enabled": bool(settings.multica_base_url),
            "up": multica_up,
        },
    }
