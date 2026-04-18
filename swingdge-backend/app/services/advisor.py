"""
Portfolio Advisor service — daily HOLD/WATCH/SELL recommendations for existing holdings.

Separate from the swing scanner. This covers positions you already own.

Decision logic (applied per holding):
  SELL  — unrealized P&L ≤ −15% AND RSI < 45 AND below SMA-50 (trend broken)
  SELL  — unrealized P&L ≤ −8%  AND price crossed below SMA-50 (breakdown)
  SELL  — unrealized P&L ≥ +25% AND RSI > 70 AND volume ratio dropping (extended, take profit)
  SELL  — earnings within 5 days (blackout — consider reducing)
  WATCH — unrealized P&L −8% to −15%, still above SMA-50 (deteriorating but not broken)
  HOLD  — unrealized P&L ≥ +15%, RSI 50–70, momentum healthy (let it run)
  HOLD  — everything else (no action needed)

Special cases:
  - Leveraged ETFs (SOXL, etc.) are excluded from standard thresholds — flagged with ⚠️ LEVERAGED_ETF
  - US-listed holdings (non-.TO) have FX cost (3% round-trip) subtracted from P&L before threshold checks
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import twelve_data, indicators as ind_svc, cache as cache_svc

settings = get_settings()

# Leveraged ETF tickers to exclude from standard logic
_LEVERAGED_ETF_KEYWORDS = {"SOXL", "TQQQ", "UPRO", "SPXL", "LABU", "TECL", "FNGU"}


@dataclass
class AdvisorResult:
    ticker: str
    account_name: str
    action: str                     # 'SELL' | 'WATCH' | 'HOLD' | 'LEVERAGED_ETF'
    reason: str
    unrealized_pnl_pct: float       # raw (before FX adjustment)
    fx_adjusted_pnl_pct: float      # after 3% round-trip deduction for US holdings
    current_price: float | None
    avg_cost: float                 # cost basis per share
    shares: float                   # position size
    rsi_14: float | None
    sma_50: float | None            # SMA-50 price level
    above_sma_50: bool | None
    macd_histogram: float | None    # positive = bullish, negative = bearish
    adx_14: float | None            # trend strength (>25 = trending)
    volume_ratio: float | None
    atr_14: float | None            # average true range (volatility)
    is_leveraged_etf: bool
    has_fx_cost: bool
    currency: str
    earnings_days_away: int | None = None
    flags: list[str] = field(default_factory=list)


async def analyze_holdings(db: AsyncSession) -> list[AdvisorResult]:
    """
    Load all holdings, fetch live data, and return advisor recommendations.
    """
    from app.services import earnings as earn_svc

    # 1. Load holdings + account names
    rows_result = await db.execute(text("""
        SELECT h.id, h.account_id, a.name AS account_name,
               h.ticker, h.exchange, h.shares, h.avg_cost,
               h.currency, h.current_price, h.sector,
               h.is_leveraged_etf, h.has_fx_cost
        FROM holdings h
        JOIN accounts a ON a.id = h.account_id
        ORDER BY h.account_id, h.ticker
    """))
    rows = rows_result.fetchall()

    if not rows:
        return []

    tickers = list({r.ticker for r in rows})

    # 2. Fetch live quotes + indicators in batch
    try:
        quotes = await twelve_data.get_batch_quotes(db, tickers)
    except Exception:
        quotes = {}

    # Get USD/CAD rate for cost basis
    usd_cad_cached = await cache_svc.cache_get(db, cache_svc.macro_key("USD_CAD"))
    usd_cad_rate: float = float(usd_cad_cached) if usd_cad_cached else 1.38

    # 3. Fetch indicators + OHLCV candles per ticker in parallel
    async def _fetch_ticker_data(ticker: str) -> tuple[str, dict, list[dict]]:
        try:
            indics = await twelve_data.get_indicators(db, ticker)
        except Exception:
            indics = {}
        try:
            candles = await twelve_data.get_daily_ohlcv(db, ticker, output_size=60)
        except Exception:
            candles = []
        return ticker, indics, candles

    ticker_data = await asyncio.gather(*[_fetch_ticker_data(t) for t in tickers])

    indicator_map: dict[str, dict] = {}
    extras_map: dict[str, dict] = {}
    for ticker, indics, candles in ticker_data:
        indicator_map[ticker] = indics
        extras_map[ticker] = ind_svc.compute_extras(candles) if candles else {}

    results: list[AdvisorResult] = []

    for row in rows:
        ticker = row.ticker
        is_leveraged = row.is_leveraged_etf or any(kw in ticker.upper() for kw in _LEVERAGED_ETF_KEYWORDS)
        has_fx = row.has_fx_cost or (not ticker.endswith(".TO") and row.currency == "USD")

        quote = quotes.get(ticker, {})
        live_price = float(quote.get("price") or row.current_price or row.avg_cost)
        indics = indicator_map.get(ticker, {})
        extras = extras_map.get(ticker, {})

        rsi = indics.get("rsi_14")
        sma_50 = indics.get("sma_50")
        above_sma_50 = (live_price > float(sma_50)) if sma_50 and live_price else None
        volume_ratio = extras.get("volume_ratio")
        macd_histogram = indics.get("macd_histogram")
        adx_14 = indics.get("adx_14")
        atr_14 = indics.get("atr_14")

        # Compute raw P&L %
        avg_cost = float(row.avg_cost)
        raw_pnl_pct = ((live_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0

        # FX-adjusted P&L: deduct 3% round-trip for US holdings
        fx_cost_pct = settings.fx_round_trip_pct if has_fx else 0.0
        adj_pnl_pct = raw_pnl_pct - fx_cost_pct

        # 5. Earnings check
        earnings_days_away: int | None = None
        earnings_in_blackout = False
        try:
            in_blackout, _earn_date, days_away = await earn_svc.is_in_blackout(db, ticker)
            earnings_days_away = days_away
            earnings_in_blackout = in_blackout
        except Exception:
            pass

        # 6. Decision logic
        if is_leveraged:
            action = "LEVERAGED_ETF"
            reason = f"Leveraged ETF — standard thresholds don't apply. P&L: {raw_pnl_pct:+.1f}%"
        elif earnings_in_blackout and earnings_days_away is not None and earnings_days_away <= 5:
            action = "SELL"
            reason = f"Earnings in {earnings_days_away}d — within blackout window, consider reducing position"
        elif adj_pnl_pct <= -15 and rsi is not None and float(rsi) < 45 and above_sma_50 is False:
            action = "SELL"
            reason = f"Trend broken: {adj_pnl_pct:+.1f}% P&L, RSI {float(rsi):.0f}, below SMA-50"
        elif adj_pnl_pct <= -8 and above_sma_50 is False:
            action = "SELL"
            reason = f"Breakdown below SMA-50 with {adj_pnl_pct:+.1f}% P&L — cut loss"
        elif adj_pnl_pct >= 25 and rsi is not None and float(rsi) > 70 and volume_ratio is not None and float(volume_ratio) < 1.0:
            action = "SELL"
            reason = f"Extended: {adj_pnl_pct:+.1f}% P&L, RSI {float(rsi):.0f}, volume fading — consider taking profit"
        elif -15 < adj_pnl_pct < -8 and above_sma_50 is True:
            action = "WATCH"
            reason = f"Deteriorating: {adj_pnl_pct:+.1f}% P&L, still above SMA-50 — monitor closely"
        elif adj_pnl_pct >= 15 and rsi is not None and 50 <= float(rsi) <= 70:
            action = "HOLD"
            reason = f"Strong momentum: {adj_pnl_pct:+.1f}% P&L, RSI {float(rsi):.0f} — let it run"
        else:
            action = "HOLD"
            reason = f"No action needed: {adj_pnl_pct:+.1f}% P&L"

        flags: list[str] = []
        if is_leveraged:
            flags.append("LEVERAGED_ETF")
        if has_fx:
            flags.append(f"FX_COST_{fx_cost_pct:.0f}PCT")
        if earnings_in_blackout:
            flags.append("EARNINGS_BLACKOUT")

        results.append(AdvisorResult(
            ticker=ticker,
            account_name=row.account_name,
            action=action,
            reason=reason,
            unrealized_pnl_pct=round(raw_pnl_pct, 2),
            fx_adjusted_pnl_pct=round(adj_pnl_pct, 2),
            current_price=live_price,
            avg_cost=avg_cost,
            shares=float(row.shares),
            rsi_14=float(rsi) if rsi is not None else None,
            sma_50=float(sma_50) if sma_50 is not None else None,
            above_sma_50=above_sma_50,
            macd_histogram=float(macd_histogram) if macd_histogram is not None else None,
            adx_14=float(adx_14) if adx_14 is not None else None,
            volume_ratio=float(volume_ratio) if volume_ratio is not None else None,
            atr_14=float(atr_14) if atr_14 is not None else None,
            is_leveraged_etf=is_leveraged,
            has_fx_cost=has_fx,
            currency=row.currency,
            earnings_days_away=earnings_days_away,
            flags=flags,
        ))

    # Sort: SELL first, then WATCH, then HOLD, then LEVERAGED_ETF
    _order = {"SELL": 0, "WATCH": 1, "HOLD": 2, "LEVERAGED_ETF": 3}
    results.sort(key=lambda r: _order.get(r.action, 4))
    return results
