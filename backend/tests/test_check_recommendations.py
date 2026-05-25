"""Tests for CheckRecommendations use case."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from daily_scheduler import tz
from daily_scheduler.application.use_cases.check_recommendations import (
    CheckRecommendations,
)
from daily_scheduler.domain.entities.recommendation import Recommendation


def _make_rec(**overrides: object) -> Recommendation:
    defaults: dict[str, object] = {
        "id": 1,
        "report_id": 1,
        "ticker": "AAPL",
        "name": "Apple",
        "market": "NASDAQ",
        "direction": "LONG",
        "timeframe": "SWING",
        "entry_price": 100.0,
        "target_price": 110.0,
        "stop_loss": 90.0,
        "status": "OPEN",
        "created_at": tz.now(),
    }
    defaults.update(overrides)
    return Recommendation(**defaults)  # type: ignore[arg-type]


class TestDayTradeExpiry:
    def test_expires_day_trade_from_previous_day(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        yesterday = tz.now() - timedelta(days=1)
        rec = _make_rec(timeframe="DAY", created_at=yesterday)
        rec_repo.get_open.return_value = [rec]

        checker = CheckRecommendations(rec_repo, finance)
        updated = checker.execute()

        assert updated == 1
        assert rec.status == "EXPIRED"
        assert rec.closed_at is not None
        rec_repo.update.assert_called_once_with(rec)

    def test_does_not_expire_same_day_trade(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        rec = _make_rec(timeframe="DAY", created_at=tz.now())
        rec_repo.get_open.return_value = [rec]
        finance.fetch_price.return_value = {"price": 105.0}

        checker = CheckRecommendations(rec_repo, finance)
        checker.execute()

        assert rec.status == "OPEN"


class TestSwingTradeExpiry:
    def test_expires_swing_trade_after_14_days(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        old = tz.now() - timedelta(days=15)
        rec = _make_rec(timeframe="SWING", created_at=old)
        rec_repo.get_open.return_value = [rec]

        checker = CheckRecommendations(rec_repo, finance)
        updated = checker.execute()

        assert updated == 1
        assert rec.status == "EXPIRED"

    def test_does_not_expire_swing_within_14_days(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        recent = tz.now() - timedelta(days=10)
        rec = _make_rec(timeframe="SWING", created_at=recent)
        rec_repo.get_open.return_value = [rec]
        finance.fetch_price.return_value = {"price": 105.0}

        checker = CheckRecommendations(rec_repo, finance)
        checker.execute()

        assert rec.status == "OPEN"


class TestLongTargetStop:
    def test_long_target_hit(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        rec = _make_rec(
            direction="LONG",
            entry_price=100.0,
            target_price=110.0,
            stop_loss=90.0,
        )
        rec_repo.get_open.return_value = [rec]
        finance.fetch_price.return_value = {"price": 112.0}

        checker = CheckRecommendations(rec_repo, finance)
        updated = checker.execute()

        assert updated == 1
        assert rec.status == "TARGET_HIT"
        assert rec.closed_price == 112.0
        assert rec.pnl_percent == pytest.approx(12.0)

    def test_long_stop_hit(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        rec = _make_rec(
            direction="LONG",
            entry_price=100.0,
            target_price=110.0,
            stop_loss=90.0,
        )
        rec_repo.get_open.return_value = [rec]
        finance.fetch_price.return_value = {"price": 88.0}

        checker = CheckRecommendations(rec_repo, finance)
        updated = checker.execute()

        assert updated == 1
        assert rec.status == "STOP_HIT"
        assert rec.closed_price == 88.0
        assert rec.pnl_percent == pytest.approx(-12.0)

    def test_long_price_in_range_stays_open(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        rec = _make_rec(direction="LONG")
        rec_repo.get_open.return_value = [rec]
        finance.fetch_price.return_value = {"price": 105.0}

        checker = CheckRecommendations(rec_repo, finance)
        updated = checker.execute()

        assert updated == 0
        assert rec.status == "OPEN"
        assert rec.current_price == 105.0


class TestShortTargetStop:
    def test_short_target_hit(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        rec = _make_rec(
            direction="SHORT",
            entry_price=100.0,
            target_price=85.0,
            stop_loss=110.0,
        )
        rec_repo.get_open.return_value = [rec]
        finance.fetch_price.return_value = {"price": 83.0}

        checker = CheckRecommendations(rec_repo, finance)
        updated = checker.execute()

        assert updated == 1
        assert rec.status == "TARGET_HIT"
        assert rec.pnl_percent == pytest.approx(17.0)

    def test_short_stop_hit(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        rec = _make_rec(
            direction="SHORT",
            entry_price=100.0,
            target_price=85.0,
            stop_loss=110.0,
        )
        rec_repo.get_open.return_value = [rec]
        finance.fetch_price.return_value = {"price": 115.0}

        checker = CheckRecommendations(rec_repo, finance)
        updated = checker.execute()

        assert updated == 1
        assert rec.status == "STOP_HIT"
        assert rec.pnl_percent == pytest.approx(-15.0)


class TestEdgeCases:
    def test_no_open_recommendations(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        rec_repo.get_open.return_value = []

        checker = CheckRecommendations(rec_repo, finance)
        updated = checker.execute()

        assert updated == 0
        finance.fetch_price.assert_not_called()

    def test_price_fetch_returns_none(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        rec = _make_rec()
        rec_repo.get_open.return_value = [rec]
        finance.fetch_price.return_value = None

        checker = CheckRecommendations(rec_repo, finance)
        updated = checker.execute()

        assert updated == 0
        assert rec.status == "OPEN"

    def test_rec_without_created_at(self):
        rec_repo = MagicMock()
        finance = MagicMock()
        rec = _make_rec(created_at=None)
        rec_repo.get_open.return_value = [rec]
        finance.fetch_price.return_value = {"price": 105.0}

        checker = CheckRecommendations(rec_repo, finance)
        checker.execute()

        assert rec.status == "OPEN"
        assert rec.current_price == 105.0
