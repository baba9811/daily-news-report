"""Report API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class ReportOut(BaseModel):
    """Report list item."""

    id: int
    report_date: date
    report_type: str
    summary: str
    generation_time_s: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportTranslationOut(BaseModel):
    """A translated rendering of a report."""

    language: str
    html_content: str

    model_config = {"from_attributes": True}


class ReportDetailOut(ReportOut):
    """Report detail with HTML content + any translated renderings.

    ``language`` is the primary (generated) language; ``translations`` carries
    the additional language renderings that power the dashboard language toggle.
    """

    html_content: str
    language: str = "ko"
    translations: list[ReportTranslationOut] = []
