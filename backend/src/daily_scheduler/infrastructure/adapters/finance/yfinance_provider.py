"""yfinance implementation of FinanceProviderPort."""

from __future__ import annotations

import logging
import math
import re
from typing import Any

import yfinance as yf

from daily_scheduler.domain.ports.finance_provider import (
    FinanceProviderPort,
)

logger = logging.getLogger(__name__)

# A bare 6-digit code is a Korean ticker (KRX) that yfinance needs suffixed
# with .KS (KOSPI) or .KQ (KOSDAQ). Council agents emit codes without suffix.
_KR_CODE = re.compile(r"^\d{6}$")


def _num(value: Any) -> float | None:
    """Coerce to float, treating None/NaN as missing."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _candidate_symbols(ticker: str) -> list[str]:
    """Yield yfinance symbols to try for a ticker.

    A bare Korean code (e.g. ``005930``) is tried as ``.KS`` then ``.KQ``;
    everything else (``005930.KS``, ``AAPL``, ``^KS11``) is used verbatim.
    """
    if _KR_CODE.match(ticker):
        return [f"{ticker}.KS", f"{ticker}.KQ"]
    return [ticker]


class YFinanceProvider(FinanceProviderPort):
    """Fetch stock and index prices via yfinance.

    Prefers ``fast_info`` (accurate ``lastPrice`` + ``previousClose`` even when
    a market is pre-open — e.g. KOSPI before 09:00 KST, where the intraday
    history bar is still NaN). Falls back to daily history when fast_info is
    unavailable, dropping incomplete (NaN) bars so the change% is computed from
    two real closes.
    """

    def fetch_price(self, ticker: str) -> dict[str, float | int] | None:
        """Fetch latest price data, trying KR suffixes for bare 6-digit codes."""
        candidates = _candidate_symbols(ticker)
        for symbol in candidates:
            result = self._fetch_one(symbol)
            if result is not None:
                return result
        logger.warning("No price data for %s (tried %s)", ticker, ", ".join(candidates))
        return None

    def _fetch_one(self, symbol: str) -> dict[str, float | int] | None:
        """Fetch a single concrete symbol; None on any failure (quietly)."""
        try:
            stock = yf.Ticker(symbol)
            from_fast = self._from_fast_info(stock)
            if from_fast is not None:
                return from_fast
            return self._from_history(stock, symbol)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.debug("fetch failed for symbol %s", symbol, exc_info=True)
            return None

    @staticmethod
    def _from_fast_info(stock: yf.Ticker) -> dict[str, float | int] | None:
        """Build a price dict from fast_info; None if essential fields missing."""
        try:
            fast = stock.fast_info
        except Exception:  # pylint: disable=broad-exception-caught
            return None

        last = _num(fast.get("lastPrice"))
        prev_close = _num(fast.get("previousClose"))
        if last is None or prev_close is None:
            return None

        return {
            "price": last,
            "open_price": _num(fast.get("open")) or last,
            "prev_close": prev_close,
            "high": _num(fast.get("dayHigh")) or last,
            "low": _num(fast.get("dayLow")) or last,
            "volume": int(_num(fast.get("lastVolume")) or 0),
        }

    @staticmethod
    def _from_history(stock: yf.Ticker, ticker: str) -> dict[str, float | int] | None:
        """Fallback: derive price from daily history, dropping NaN bars."""
        hist = stock.history(period="5d").dropna()
        if hist.empty:
            logger.warning("No data returned for %s", ticker)
            return None
        latest = hist.iloc[-1]
        if len(hist) >= 2:
            prev_close = float(hist.iloc[-2]["Close"])
        else:
            prev_close = float(latest["Open"])
        return {
            "price": float(latest["Close"]),
            "open_price": float(latest["Open"]),
            "prev_close": prev_close,
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "volume": int(latest["Volume"]),
        }
