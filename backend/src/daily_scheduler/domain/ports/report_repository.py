"""Port: report persistence interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from daily_scheduler.domain.entities.report import Report, ReportTranslation


class ReportRepositoryPort(ABC):
    """Abstract interface for report persistence."""

    @abstractmethod
    def get_by_id(self, report_id: int) -> Report | None:
        """Return a report by its ID."""

    @abstractmethod
    def get_latest(
        self,
        report_type: str = "daily",
    ) -> Report | None:
        """Return the most recent report of the given type."""

    @abstractmethod
    def get_by_date(
        self,
        report_date: date,
        report_type: str = "daily",
    ) -> Report | None:
        """Return a report for the given date and type."""

    @abstractmethod
    def list_reports(
        self,
        report_type: str = "all",
        page: int = 1,
        per_page: int = 20,
    ) -> list[Report]:
        """Return a paginated list of reports."""

    @abstractmethod
    def save(self, report: Report) -> Report:
        """Persist a report."""

    @abstractmethod
    def save_translation(self, translation: ReportTranslation) -> ReportTranslation:
        """Persist (upsert by report_id + language) a report translation."""

    @abstractmethod
    def get_translations(self, report_id: int) -> list[ReportTranslation]:
        """Return all stored translations for a report."""
