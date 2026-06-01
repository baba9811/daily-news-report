"""Port: news/report generation provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date


class NewsProviderPort(ABC):
    """Abstract interface for generating reports (e.g. via Claude)."""

    @abstractmethod
    def generate_daily_report(
        self,
        report_date: date,
        retrospective_context: str,
        weekly_lessons: str = "",
        market_data: str = "",
        screening_data: str = "",
    ) -> tuple[str, float]:
        """Generate a daily report.

        Args:
            report_date: The date for the report.
            retrospective_context: Past recommendation performance data.
            weekly_lessons: Weekly analysis text (Mondays only).
            market_data: Pre-fetched real-time market data text.
            screening_data: Pre-screened stock universe with fundamentals/technicals.

        Returns (raw_response, generation_time_seconds).
        """

    @abstractmethod
    def generate_weekly_report(
        self,
        report_date: date,
        weekly_stats: str,
        detailed_performance: str,
        closed_rationales: str = "",
    ) -> tuple[str, float]:
        """Generate a weekly retrospective report.

        Args:
            report_date: The date for the report.
            weekly_stats: Summary stats (wins, losses, avg return).
            detailed_performance: Sector breakdown JSON.
            closed_rationales: Original rationale for each closed trade.

        Returns (raw_response, generation_time_seconds).
        """
