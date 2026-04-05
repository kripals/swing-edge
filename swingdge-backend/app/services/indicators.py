"""
Local indicator calculations from OHLCV candles.

EMA, SMA, RSI, MACD, Bollinger Bands, and ATR come from Twelve Data via
twelve_data.get_indicators(). This module computes the three indicators
that require full candle history and are not worth a separate API call:

  - VWAP          — volume-weighted average price (last N candles)
  - volume_ratio  — today's volume / 20-day average volume
  - relative_strength — % gain vs TSX Composite (^GSPTSE) over 20 days

Usage:
    candles = await twelve_data.get_daily_ohlcv(db, ticker, output_size=60)
    extras = compute_extras(candles)
    # extras = {"vwap": 42.31, "volume_ratio": 1.73, "relative_strength": 3.21}

Candle format (Twelve Data time_series values):
    {"datetime": "2024-01-15", "open": "...", "high": "...",
     "low": "...", "close": "...", "volume": "..."}
"""
from __future__ import annotations

from typing import Any


def _f(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def compute_vwap(candles: list[dict], n: int = 20) -> float | None:
    """
    VWAP over the last N candles.
    Uses (high+low+close)/3 as typical price per candle.
    """
    recent = candles[:n]  # candles are newest-first from Twelve Data
    if not recent:
        return None
    total_pv = sum(_f(c["high"]) + _f(c["low"]) + _f(c["close"]) for c in recent) / 3
    total_v = sum(_f(c["volume"]) for c in recent)
    if total_v == 0:
        return None
    # Weighted: sum(typical_price * volume) / sum(volume)
    pv_vol = sum(
        ((_f(c["high"]) + _f(c["low"]) + _f(c["close"])) / 3) * _f(c["volume"])
        for c in recent
    )
    return round(pv_vol / total_v, 4)


def compute_volume_ratio(candles: list[dict], avg_period: int = 20) -> float | None:
    """
    Today's volume / N-day average volume.
    candles[0] = most recent (today).
    """
    if len(candles) < 2:
        return None
    today_vol = _f(candles[0]["volume"])
    avg_vols = [_f(c["volume"]) for c in candles[1 : avg_period + 1]]
    if not avg_vols:
        return None
    avg = sum(avg_vols) / len(avg_vols)
    if avg == 0:
        return None
    return round(today_vol / avg, 2)


def compute_relative_strength(
    ticker_candles: list[dict],
    benchmark_candles: list[dict],
    period: int = 20,
) -> float | None:
    """
    Relative strength = ticker % change over period  minus  benchmark % change.
    Positive = outperforming TSX Composite.
    """
    if len(ticker_candles) < period or len(benchmark_candles) < period:
        return None

    t_now = _f(ticker_candles[0]["close"])
    t_then = _f(ticker_candles[period - 1]["close"])
    b_now = _f(benchmark_candles[0]["close"])
    b_then = _f(benchmark_candles[period - 1]["close"])

    if t_then == 0 or b_then == 0:
        return None

    ticker_chg = (t_now - t_then) / t_then * 100
    bench_chg = (b_now - b_then) / b_then * 100
    return round(ticker_chg - bench_chg, 2)


def compute_extras(
    candles: list[dict],
    benchmark_candles: list[dict] | None = None,
) -> dict[str, float | None]:
    """
    Compute VWAP, volume_ratio, and optionally relative_strength.
    Returns a dict ready to merge into the indicators dict.
    """
    result: dict[str, float | None] = {
        "vwap": compute_vwap(candles),
        "volume_ratio": compute_volume_ratio(candles),
        "relative_strength": None,
    }
    if benchmark_candles:
        result["relative_strength"] = compute_relative_strength(candles, benchmark_candles)
    return result
