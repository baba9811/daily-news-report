"""SQLAlchemy implementation of ReportRepositoryPort."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from daily_scheduler.domain.entities.report import Report, ReportTranslation
from daily_scheduler.domain.ports.report_repository import (
    ReportRepositoryPort,
)
from daily_scheduler.infrastructure.adapters.persistence.models import (
    ReportModel,
    ReportTranslationModel,
)


class SQLAlchemyReportRepository(ReportRepositoryPort):
    """Persist reports via SQLAlchemy."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, report_id: int) -> Report | None:
        model = self._db.query(ReportModel).filter(ReportModel.id == report_id).first()
        return model.to_entity() if model else None

    def get_latest(
        self,
        report_type: str = "daily",
    ) -> Report | None:
        model = (
            self._db.query(ReportModel)
            .filter(ReportModel.report_type == report_type)
            .order_by(ReportModel.created_at.desc())
            .first()
        )
        return model.to_entity() if model else None

    def get_by_date(
        self,
        report_date: date,
        report_type: str = "daily",
    ) -> Report | None:
        model = (
            self._db.query(ReportModel)
            .filter(
                ReportModel.report_date == report_date,
                ReportModel.report_type == report_type,
            )
            .first()
        )
        return model.to_entity() if model else None

    def list_reports(
        self,
        report_type: str = "all",
        page: int = 1,
        per_page: int = 20,
    ) -> list[Report]:
        query = self._db.query(ReportModel)
        if report_type != "all":
            query = query.filter(
                ReportModel.report_type == report_type,
            )
        query = query.order_by(ReportModel.created_at.desc())
        models = query.offset((page - 1) * per_page).limit(per_page).all()
        return [m.to_entity() for m in models]

    def save(self, report: Report) -> Report:
        model = ReportModel.from_entity(report)
        self._db.add(model)
        self._db.flush()
        self._db.commit()
        return model.to_entity()

    def save_translation(self, translation: ReportTranslation) -> ReportTranslation:
        existing = (
            self._db.query(ReportTranslationModel)
            .filter(
                ReportTranslationModel.report_id == translation.report_id,
                ReportTranslationModel.language == translation.language,
            )
            .first()
        )
        if existing is not None:
            existing.html_content = translation.html_content
            existing.summary = translation.summary
            model = existing
        else:
            model = ReportTranslationModel(
                report_id=translation.report_id,
                language=translation.language,
                html_content=translation.html_content,
                summary=translation.summary,
            )
            self._db.add(model)
        self._db.flush()
        self._db.commit()
        return model.to_entity()

    def get_translations(self, report_id: int) -> list[ReportTranslation]:
        models = (
            self._db.query(ReportTranslationModel)
            .filter(ReportTranslationModel.report_id == report_id)
            .order_by(ReportTranslationModel.language)
            .all()
        )
        return [m.to_entity() for m in models]
