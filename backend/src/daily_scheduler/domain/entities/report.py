"""Report entity — pure Python dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Report:
    """A generated daily or weekly report."""

    report_date: date
    report_type: str = "daily"  # "daily" or "weekly"
    html_content: str = ""
    summary: str = ""
    prompt_used: str = ""
    raw_response: str = ""
    generation_time_s: float | None = None
    id: int | None = None
    created_at: datetime | None = field(default=None)


@dataclass
class ReportTranslation:
    """A translated rendering of a report in a target language."""

    language: str
    html_content: str = ""
    summary: str = ""
    report_id: int | None = None
    id: int | None = None
    created_at: datetime | None = field(default=None)
