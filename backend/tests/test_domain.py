"""Tests for domain entities."""

from __future__ import annotations

from datetime import date

from daily_scheduler.domain.entities.recommendation import (
    Recommendation,
)
from daily_scheduler.domain.entities.report import Report


class TestRecommendationEntity:
    def test_create_recommendation(self):
        rec = Recommendation(
            id=None,
            report_id=1,
            ticker="AAPL",
            name="Apple Inc.",
            market="NASDAQ",
            direction="LONG",
            timeframe="SWING",
            entry_price=185.0,
            target_price=195.0,
            stop_loss=180.0,
        )
        assert rec.status == "OPEN"
        assert rec.pnl_percent is None
        assert rec.ticker == "AAPL"

    def test_default_values(self):
        rec = Recommendation(
            id=None,
            report_id=1,
            ticker="T",
            name="Test",
            market="NYSE",
            direction="LONG",
            timeframe="DAY",
            entry_price=100.0,
            target_price=110.0,
            stop_loss=95.0,
        )
        assert rec.rationale == ""
        assert rec.sector == ""
        assert rec.current_price is None


class TestReportEntity:
    def test_create_report(self):
        report = Report(
            id=None,
            report_date=date(2026, 3, 17),
            report_type="daily",
            html_content="<html>test</html>",
            summary="Test summary",
        )
        assert report.report_type == "daily"
        assert report.report_date == date(2026, 3, 17)
