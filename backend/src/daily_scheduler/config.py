"""Central configuration using pydantic-settings. Reads from .env at project root."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # daily-scheduler/
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    email_from: str = ""
    email_to: list[str] = []

    # Claude
    claude_cli_path: str = "claude"
    claude_model: str = "sonnet"

    # Codex — gpt-5.5 is the default model available on a ChatGPT subscription
    # (gpt-5-codex is API-only and is rejected by `codex exec` under ChatGPT auth)
    codex_cli_path: str = "codex"
    codex_default_model: str = "gpt-5.5"

    # Finance (optional)
    news_api_key: SecretStr = SecretStr("")
    alphavantage_key: SecretStr = SecretStr("")

    # Database
    database_url: str = f"sqlite:///{PROJECT_ROOT}/data/daily_scheduler.db"

    # Report
    report_language: str = "ko"
    # Secondary language for a translated copy of each report (separate email +
    # dashboard toggle). Empty or equal to report_language disables bilingual.
    report_secondary_language: str = "en"

    # Timezone (IANA format, e.g. Asia/Seoul, US/Eastern, UTC)
    timezone: str = "Asia/Seoul"

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Multica integration (Plan 4)
    # base_url = backend API (issues/comments/health); web_url = the Next.js
    # board UI embedded as an iframe on the /multica page.
    multica_base_url: str = ""
    multica_web_url: str = ""
    multica_webhook_secret: str = ""
    # Outbound auth: a Personal Access Token (mul_...) + the target workspace
    # UUID. Both are required to create issues/comments; without them the
    # outbound integration stays disabled (health probe still works).
    multica_api_token: str = ""
    multica_workspace_id: str = ""

    @field_validator("email_to", mode="before")
    @classmethod
    def parse_email_to(cls, v: str | list[str]) -> list[str]:
        """Parse email_to from JSON string or list."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            return [v] if v else []
        return v

    @property
    def db_path(self) -> Path:
        """Return the database file path."""
        url = self.database_url.replace("sqlite:///", "")
        path = Path(url)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path


def get_settings() -> Settings:
    """Create and return a Settings instance."""
    return Settings()
