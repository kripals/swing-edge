"""
Scanner engine — runs all filter criteria and scores each passing ticker.

Flow per ticker:
  1. Basic filters  (price, avg volume, market cap, not leveraged ETF)
  2. Earnings blackout check
  3. Fetch indicators (Twelve Data API + local extras)
  4. Trend filter      (price > SMA 50)
  5. Signal detection  (RSI pullback, MACD crossover, EMA crossover, etc.)
  6. Score calculation (0.0–1.0)
  7. Return ScanCandidate if score >= threshold (0.4)

Signal types (from architecture v3 section 12):
  RSI_PULLBACK    — uptrend + RSI 30-50
  RSI_REVERSAL    — RSI crossed above 30
  MACD_CROSSOVER  — histogram turned positive
  EMA_CROSSOVER   — EMA9 crossed above EMA21
  BB_BOUNCE       — price near lower Bollinger Band
  VOLUME_BREAKOUT — broke resistance on >2x volume
  COMBO           — two or more signals at once
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticker import Ticker
from app.services import rules as rules_svc
from app.services import indicators as ind_svc
from app.services import earnings as earn_svc
from app.services import twelve_data

logger = logging.getLogger(__name__)


@dataclass
class ScanCandidate:
    ticker: str
    exchange: str
    sector: str | None
    current_price: float | None
    signal_type: str
    signal_strength: float          # 0.0–1.0
    signals: list[str]              # individual signals that fired
    rsi_14: float | None
    macd_histogram: float | None
    volume_ratio: float | None
    above_sma_50: bool
    atr_14: float | None
    relative_strength: float | None
    earnings_date: date | None
    earnings_days_away: int | None
    notes: str = ""


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_scan(db: AsyncSession) -> list[ScanCandidate]:
    """
    Scan all active tickers. Returns list of candidates sorted by signal_strength desc.
    Skips leveraged ETFs and tickers in earnings blackout.
    """
    tickers = await _get_active_tickers(db)
    if not tickers:
        return []

    # Fetch quotes for all tickers in one batch call
    ticker_symbols = [t.ticker for t in tickers]
    quotes = await twelve_data.get_batch_quotes(db, ticker_symbols)

    # Pre-fetch benchmark (TSX Composite) candles for relative strength
    benchmark_candles = await _fetch_benchmark(db)

    # Fetch rules once (they're cached in-memory by rules_svc)
    min_price = await rules_svc.scanner_min_price(db)
    min_avg_vol = await rules_svc.scanner_min_avg_volume(db)

    # Scan each ticker — gather with limited concurrency to respect API rate limits
    semaphore = asyncio.Semaphore(5)  # max 5 concurrent API calls

    async def scan_one(t: Ticker) -> ScanCandidate | None:
        async with semaphore:
            return await _scan_ticker(db, t, quotes, benchmark_candles, min_price, min_avg_vol)

    results = await asyncio.gather(*[scan_one(t) for t in tickers], return_exceptions=True)

    errors = [r for r in results if isinstance(r, Exception)]
    candidates = [r for r in results if isinstance(r, ScanCandidate)]
    candidates.sort(key=lambda c: c.signal_strength, reverse=True)

    logger.info(
        "Scan complete: %d tickers, %d candidates, %d errors",
        len(tickers), len(candidates), len(errors),
    )
    if errors:
        logger.warning("Scan errors (first 3): %s", [str(e) for e in errors[:3]])

    return candidates


# ── Per-ticker scan ───────────────────────────────────────────────────────────

async def _scan_ticker(
    db: AsyncSession,
    ticker_row: Ticker,
    quotes: dict[str, dict],
    benchmark_candles: list[dict],
    min_price: float,
    min_avg_vol: int,
) -> ScanCandidate | None:
    ticker = ticker_row.ticker

    # ── 1. Quote check ────────────────────────────────────────────────────────
    quote = quotes.get(ticker, {})
    price = quote.get("price")
    if price is None or price < min_price:
        logger.debug("%s: filtered — no quote or price $%.2f < min $%.2f", ticker, price or 0, min_price)
        return None

    # ── 2. Volume pre-filter — reject before spending any API quota ──────────────
    if quote.get("volume", 0) < min_avg_vol:
        logger.debug("%s: filtered — volume %d < min %d", ticker, quote.get("volume", 0), min_avg_vol)
        return None

    # ── 3. Earnings blackout ──────────────────────────────────────────────────
    in_blackout, earnings_date, days_away = await earn_svc.is_in_blackout(db, ticker)
    if in_blackout:
        logger.debug("%s: filtered — earnings blackout (%s, %d days)", ticker, earnings_date, days_away or 0)
        return None

    # ── 4. Indicators (API-based) ─────────────────────────────────────────────
    try:
        ind = await twelve_data.get_indicators(db, ticker)
    except Exception as exc:
        logger.warning("%s: filtered — indicators failed: %s", ticker, exc)
        return None

    if not ind:
        logger.debug("%s: filtered — empty indicators", ticker)
        return None

    # ── 5. OHLCV for local extras ─────────────────────────────────────────────
    try:
        candles = await twelve_data.get_daily_ohlcv(db, ticker, output_size=60)
    except Exception:
        candles = []

    extras = ind_svc.compute_extras(candles, benchmark_candles)
    ind.update(extras)
    volume_ratio = ind.get("volume_ratio")

    # ── 6. Trend filter: price must be above SMA 50 ───────────────────────────
    sma_50 = ind.get("sma_50")
    above_sma_50 = sma_50 is not None and price > sma_50

    # ── 7. Signal detection ───────────────────────────────────────────────────
    signals = _detect_signals(price, ind, above_sma_50)
    if not signals:
        logger.debug("%s: filtered — no signals (above_sma50=%s, rsi=%.1f, macd_hist=%.4f)",
                     ticker, above_sma_50,
                     ind.get("rsi_14") or 0,
                     ind.get("macd_histogram") or 0)
        return None

    # ── 8. Scoring ────────────────────────────────────────────────────────────
    score = _score(price, ind, above_sma_50, volume_ratio)
    if score < 0.4:
        logger.debug("%s: filtered — score %.2f < 0.4 (signals=%s)", ticker, score, signals)
        return None

    signal_type = _pick_signal_type(signals)

    return ScanCandidate(
        ticker=ticker,
        exchange=ticker_row.exchange,
        sector=ticker_row.sector,
        current_price=price,
        signal_type=signal_type,
        signal_strength=round(score, 2),
        signals=signals,
        rsi_14=ind.get("rsi_14"),
        macd_histogram=ind.get("macd_histogram"),
        volume_ratio=volume_ratio,
        above_sma_50=above_sma_50,
        atr_14=ind.get("atr_14"),
        relative_strength=ind.get("relative_strength"),
        earnings_date=earnings_date,
        earnings_days_away=days_away,
    )


# ── Signal detection ──────────────────────────────────────────────────────────

def _detect_signals(price: float, ind: dict, above_sma_50: bool) -> list[str]:
    signals: list[str] = []

    rsi = ind.get("rsi_14")
    macd_hist = ind.get("macd_histogram")
    ema9 = ind.get("ema_9")
    ema21 = ind.get("ema_21")
    ema9_yesterday = ind.get("ema_9_yesterday")
    ema21_yesterday = ind.get("ema_21_yesterday")
    bb_lower = ind.get("bb_lower")
    volume_ratio = ind.get("volume_ratio")
    sma_200 = ind.get("sma_200")

    # RSI_PULLBACK: confirmed uptrend (above SMA50) + RSI pulled back to 30-50 buy zone
    if above_sma_50 and rsi is not None and 30 <= rsi <= 50:
        signals.append("RSI_PULLBACK")

    # RSI_REVERSAL: stock NOT yet in uptrend, RSI recovering from oversold (30-35).
    # Deliberately excludes above_sma_50 stocks — those get RSI_PULLBACK instead.
    # Prevents both signals firing simultaneously on the same RSI reading.
    if not above_sma_50 and rsi is not None and 30 <= rsi <= 35:
        signals.append("RSI_REVERSAL")

    # MACD_CROSSOVER: histogram positive AND at least 0.5% of price in magnitude.
    # Filters noise — a near-zero crossing on a choppy stock is not a real signal.
    if macd_hist is not None and macd_hist > price * 0.005:
        signals.append("MACD_CROSSOVER")

    # EMA_CROSSOVER: EMA9 *just* crossed above EMA21 today.
    # Requires yesterday's EMA9 <= EMA21 so weeks-long uptrends don't keep re-firing.
    # Falls back to gap heuristic (≤2%) if yesterday's values unavailable.
    ema_crossed_today = (
        ema9_yesterday is not None and ema21_yesterday is not None
        and ema9_yesterday <= ema21_yesterday
    )
    ema_gap_fresh = (
        ema9_yesterday is None
        and ema9 is not None and ema21 is not None and ema21 > 0
        and (ema9 - ema21) / ema21 <= 0.02
    )
    if ema9 is not None and ema21 is not None and ema9 > ema21 and (ema_crossed_today or ema_gap_fresh):
        signals.append("EMA_CROSSOVER")

    # BB_BOUNCE: price within 2% of lower Bollinger Band
    if bb_lower is not None and price <= bb_lower * 1.02:
        signals.append("BB_BOUNCE")

    # VOLUME_BREAKOUT: strong volume + price above SMA50 + above SMA200
    if (volume_ratio is not None and volume_ratio >= 2.0
            and above_sma_50
            and sma_200 is not None and price > sma_200):
        signals.append("VOLUME_BREAKOUT")

    return signals


def _pick_signal_type(signals: list[str]) -> str:
    if len(signals) >= 2:
        return "COMBO"
    return signals[0] if signals else "UNKNOWN"


# ── Scoring (architecture v3 section 12) ─────────────────────────────────────

def _score(price: float, ind: dict, above_sma_50: bool, volume_ratio: float | None) -> float:
    """
    Each component is 0 or 1. Score = sum / total (9 components).
    Must be >= 0.4 to pass.
    """
    components = [
        above_sma_50,                                                               # price > SMA 50
        ind.get("sma_200") is not None and price > ind["sma_200"],                  # price > SMA 200
        ind.get("rsi_14") is not None and 30 <= ind["rsi_14"] <= 50,                # RSI in buy zone
        ind.get("macd_histogram") is not None and ind["macd_histogram"] > price * 0.005,  # MACD hist positive (min 0.5% of price)
        volume_ratio is not None and volume_ratio >= 1.5,                           # volume spike
        ind.get("ema_9") is not None and ind.get("ema_21") is not None
            and ind["ema_21"] > 0 and ind["ema_9"] > ind["ema_21"]
            and (ind["ema_9"] - ind["ema_21"]) / ind["ema_21"] <= 0.02,             # EMA9 freshly above EMA21 (within 2%)
        ind.get("bb_lower") is not None and price <= ind["bb_lower"] * 1.02,        # near BB lower
        ind.get("relative_strength") is not None and ind["relative_strength"] > 0,  # RS > 0
        # news sentiment — not implemented yet, always False
        False,
    ]
    return sum(1 for c in components if c) / len(components)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_active_tickers(db: AsyncSession) -> list[Ticker]:
    result = await db.execute(
        select(Ticker).where(Ticker.is_active == True)
    )
    return result.scalars().all()


async def _fetch_benchmark(db: AsyncSession) -> list[dict]:
    """Fetch TSX Composite candles for relative strength calculation."""
    try:
        return await twelve_data.get_daily_ohlcv(db, "^GSPTSE", output_size=60)
    except Exception:
        return []
