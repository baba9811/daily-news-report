"""Reports router — list and view generated reports."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from daily_scheduler import tz
from daily_scheduler.config import get_settings
from daily_scheduler.database import get_db
from daily_scheduler.domain.entities.report import Report
from daily_scheduler.domain.ports.report_repository import ReportRepositoryPort
from daily_scheduler.entrypoints.api.schemas.report import (
    ReportDetailOut,
    ReportOut,
    ReportTranslationOut,
)
from daily_scheduler.infrastructure.dependencies import (
    get_report_repo,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _to_detail(report: Report, repo: ReportRepositoryPort) -> ReportDetailOut:
    """Build a detail DTO, attaching any stored translations for the toggle."""
    translations = repo.get_translations(report.id) if report.id else []
    return ReportDetailOut(
        id=report.id or 0,
        report_date=report.report_date,
        report_type=report.report_type,
        summary=report.summary,
        generation_time_s=report.generation_time_s,
        created_at=report.created_at or tz.now(),
        html_content=report.html_content,
        language=get_settings().report_language,
        translations=[
            ReportTranslationOut(language=t.language, html_content=t.html_content)
            for t in translations
        ],
    )


@router.get("", response_model=list[ReportOut])
def list_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    report_type: str = Query("all"),
    db: Session = Depends(get_db),
) -> list[ReportOut]:
    """List reports with pagination."""
    repo = get_report_repo(db)
    reports = repo.list_reports(
        report_type=report_type,
        page=page,
        per_page=per_page,
    )
    return [
        ReportOut(
            id=r.id or 0,
            report_date=r.report_date,
            report_type=r.report_type,
            summary=r.summary,
            generation_time_s=r.generation_time_s,
            created_at=r.created_at or tz.now(),
        )
        for r in reports
    ]


@router.get("/latest", response_model=ReportDetailOut)
def get_latest_report(
    db: Session = Depends(get_db),
) -> ReportDetailOut:
    """Get the latest daily report."""
    repo = get_report_repo(db)
    report = repo.get_latest("daily")
    if not report:
        raise HTTPException(
            status_code=404,
            detail="No reports found",
        )
    return _to_detail(report, repo)


@router.get("/{report_id}", response_model=ReportDetailOut)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
) -> ReportDetailOut:
    """Get a specific report by ID."""
    repo = get_report_repo(db)
    report = repo.get_by_id(report_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found",
        )
    return _to_detail(report, repo)


@router.get(
    "/{report_id}/html",
    response_class=HTMLResponse,
)
def get_report_html(
    report_id: int,
    lang: str = Query("", description="Language code; serves a translation when set"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Get raw HTML content of a report, optionally in a translated language."""
    repo = get_report_repo(db)
    report = repo.get_by_id(report_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found",
        )
    if lang and lang != get_settings().report_language:
        for translation in repo.get_translations(report_id):
            if translation.language == lang:
                return HTMLResponse(content=translation.html_content)
    return HTMLResponse(content=report.html_content)
