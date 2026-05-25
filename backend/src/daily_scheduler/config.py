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

    # Codex
    codex_cli_path: str = "codex"
    codex_default_model: str = "gpt-5-codex"

    # Finance (optional)
    news_api_key: SecretStr = SecretStr("")
    alphavantage_key: SecretStr = SecretStr("")

    # Database
    database_url: str = f"sqlite:///{PROJECT_ROOT}/data/daily_scheduler.db"

    # Report
    report_language: str = "ko"

    # Timezone (IANA format, e.g. Asia/Seoul, US/Eastern, UTC)
    timezone: str = "Asia/Seoul"

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

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
