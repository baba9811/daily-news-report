"""Tests for database ORM models."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from daily_scheduler import tz
from daily_scheduler.infrastructure.adapters.persistence.models import (
    RecommendationModel,
    ReportModel,
)


class TestReportModel:
    def test_create_report(self, db: Session):
        report = ReportModel(
            report_date=date(2026, 3, 17),
            report_type="daily",
            html_content="<html>test</html>",
            summary="Test report",
        )
        db.add(report)
        db.commit()

        fetched = db.query(ReportModel).first()
        assert fetched is not None
        assert fetched.report_date == date(2026, 3, 17)
        assert fetched.report_type == "daily"

    def test_report_recommendation_relationship(self, db: Session):
        report = ReportModel(
            report_date=date(2026, 3, 17),
            report_type="daily",
        )
        db.add(report)
        db.flush()

        rec = RecommendationModel(
            report_id=report.id,
            ticker="AAPL",
            name="Apple Inc.",
            market="NASDAQ",
            direction="LONG",
            timeframe="SWING",
            entry_price=185.0,
            target_price=195.0,
            stop_loss=180.0,
        )
        db.add(rec)
        db.commit()

        fetched = db.query(ReportModel).first()
        assert fetched is not None
        assert len(fetched.recommendations) == 1
        assert fetched.recommendations[0].ticker == "AAPL"


class TestRecommendationModel:
    def test_default_status_is_open(self, db: Session):
        report = ReportModel(
            report_date=date(2026, 3, 17),
            report_type="daily",
        )
        db.add(report)
        db.flush()

        rec = RecommendationModel(
            report_id=report.id,
            ticker="TSLA",
            name="Tesla",
            market="NASDAQ",
            direction="LONG",
            timeframe="DAY",
            entry_price=250.0,
            target_price=260.0,
            stop_loss=245.0,
        )
        db.add(rec)
        db.commit()

        fetched = db.query(RecommendationModel).first()
        assert fetched is not None
        assert fetched.status == "OPEN"
        assert fetched.pnl_percent is None

    def test_close_recommendation(self, db: Session):
        report = ReportModel(
            report_date=date(2026, 3, 17),
            report_type="daily",
        )
        db.add(report)
        db.flush()

        rec = RecommendationModel(
            report_id=report.id,
            ticker="AAPL",
            name="Apple",
            market="NASDAQ",
            direction="LONG",
            timeframe="SWING",
            entry_price=185.0,
            target_price=195.0,
            stop_loss=180.0,
        )
        db.add(rec)
        db.commit()

        rec.status = "TARGET_HIT"
        rec.closed_at = tz.now()
        rec.closed_price = 196.0
        rec.pnl_percent = 5.95
        db.commit()

        fetched = db.query(RecommendationModel).first()
        assert fetched is not None
        assert fetched.status == "TARGET_HIT"
        assert fetched.pnl_percent == 5.95
