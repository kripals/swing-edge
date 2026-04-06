"""
Market intelligence service — orchestrates macro + sector data.

Aggregates data from:
  - Bank of Canada Valet API (overnight rate, USD/CAD, CPI)
  - Alpha Vantage (WTI oil, gold, natural gas, copper)
  - Twelve Data (sector ETF quotes for rotation tracker)
  - FMP (company fundamentals + analyst ratings)
  - Finnhub (earnings calendar)

Sector ETFs tracked (TSX-listed):
  XEG.TO  — Energy
  ZEB.TO  — Financials (banks)
  XGD.TO  — Gold Miners
  ZRE.TO  — REITs
  XIT.TO  — Technology
  ZUT.TO  — Utilities
  XMA.TO  — Materials
  XHC.TO  — Healthcare
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import boc as boc_svc
from app.services import alpha_vantage as av_svc
from app.services import twelve_data
from app.services import fmp as fmp_svc
from app.services import finnhub as fh_svc
from app.services import earnings as earn_svc


# ── Sector ETF universe ───────────────────────────────────────────────────────

SECTOR_ETFS = [
    {"ticker": "XEG.TO", "sector": "Energy",      "name": "iShares S&P/TSX Capped Energy"},
    {"ticker": "ZEB.TO", "sector": "Financials",   "name": "BMO Equal Weight Banks"},
    {"ticker": "XGD.TO", "sector": "Gold Miners",  "name": "iShares S&P/TSX Global Gold"},
    {"ticker": "ZRE.TO", "sector": "REITs",        "name": "BMO Equal Weight REITs"},
    {"ticker": "XIT.TO", "sector": "Technology",   "name": "iShares S&P/TSX Capped Info Tech"},
    {"ticker": "ZUT.TO", "sector": "Utilities",    "name": "BMO Equal Weight Utilities"},
    {"ticker": "XMA.TO", "sector": "Materials",    "name": "iShares S&P/TSX Capped Materials"},
    {"ticker": "XHC.TO", "sector": "Healthcare",   "name": "iShares S&P/TSX Capped Health Care"},
]


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class MacroSnapshot:
    overnight_rate: dict | None
    usd_cad: dict | None
    cpi: dict | None
    wti_oil: float | None
    gold: float | None
    natural_gas: float | None
    copper: float | None


@dataclass
class SectorPerformance:
    ticker: str
    sector: str
    name: str
    price: float | None
    change_pct: float | None
    volume: int | None


@dataclass
class TickerFundamentals:
    ticker: str
    profile: dict | None
    analyst_ratings: dict | None
    earnings_history: list[dict] = field(default_factory=list)
    next_earnings_date: str | None = None
    earnings_days_away: int | None = None


# ── Macro snapshot ────────────────────────────────────────────────────────────

async def get_macro(db: AsyncSession) -> MacroSnapshot:
    """
    Fetch all macro data concurrently. Individual failures return None rather
    than failing the whole request — macro context is supplemental.
    """
    async def safe(coro):
        try:
            return await coro
        except Exception:
            return None

    overnight, usd_cad, cpi, wti, gold, nat_gas, copper = await asyncio.gather(
        safe(boc_svc.get_overnight_rate(db)),
        safe(boc_svc.get_usd_cad(db)),
        safe(boc_svc.get_cpi(db)),
        safe(av_svc.get_wti_oil(db)),
        safe(av_svc.get_gold(db)),
        safe(av_svc.get_natural_gas(db)),
        safe(av_svc.get_copper(db)),
    )

    # Wrap raw floats from Alpha Vantage in dicts for consistent frontend shape
    def _wrap_commodity(value: float | None, label: str, unit: str) -> dict | None:
        if value is None:
            return None
        return {"value": value, "label": label, "unit": unit}

    return MacroSnapshot(
        overnight_rate=overnight,
        usd_cad=usd_cad,
        cpi=cpi,
        wti_oil=_wrap_commodity(wti, "WTI Crude Oil", "USD/bbl"),
        gold=_wrap_commodity(gold, "Gold", "USD/oz"),
        natural_gas=_wrap_commodity(nat_gas, "Natural Gas", "USD/MMBtu"),
        copper=_wrap_commodity(copper, "Copper", "USD/lb"),
    )


# ── Sector rotation ───────────────────────────────────────────────────────────

async def get_sectors(db: AsyncSession) -> list[SectorPerformance]:
    """
    Fetch quotes for all sector ETFs. Returns them sorted by change_pct desc
    (best performing sector first).
    """
    tickers = [e["ticker"] for e in SECTOR_ETFS]
    quotes = await twelve_data.get_batch_quotes(db, tickers)

    results = []
    for etf in SECTOR_ETFS:
        q = quotes.get(etf["ticker"], {})
        results.append(SectorPerformance(
            ticker=etf["ticker"],
            sector=etf["sector"],
            name=etf["name"],
            price=q.get("price"),
            change_pct=q.get("percent_change"),
            volume=q.get("volume"),
        ))

    # Sort by change_pct desc, putting None last
    results.sort(key=lambda s: s.change_pct if s.change_pct is not None else -999, reverse=True)
    return results


# ── Ticker fundamentals ───────────────────────────────────────────────────────

async def get_fundamentals(db: AsyncSession, ticker: str) -> TickerFundamentals:
    """
    Fetch full fundamental picture for a ticker: profile, analyst ratings,
    earnings history, next earnings date.
    """
    async def safe(coro):
        try:
            return await coro
        except Exception:
            return None

    profile, ratings, earnings_hist, earnings_check = await asyncio.gather(
        safe(fmp_svc.get_profile(db, ticker)),
        safe(fmp_svc.get_analyst_ratings(db, ticker)),
        safe(fmp_svc.get_earnings_history(db, ticker, limit=4)),
        safe(earn_svc.is_in_blackout(db, ticker)),
    )

    next_earnings_date = None
    days_away = None
    if earnings_check:
        _, next_earnings_date, days_away = earnings_check
        if next_earnings_date:
            next_earnings_date = next_earnings_date.isoformat()

    return TickerFundamentals(
        ticker=ticker,
        profile=profile,
        analyst_ratings=ratings,
        earnings_history=earnings_hist or [],
        next_earnings_date=next_earnings_date,
        earnings_days_away=days_away,
    )


# ── Quote with context ────────────────────────────────────────────────────────

async def get_quote_with_context(db: AsyncSession, ticker: str) -> dict:
    """
    Rich quote: price data from Twelve Data + Finnhub supplemental fields.
    """
    quotes, fh_quote = await asyncio.gather(
        twelve_data.get_batch_quotes(db, [ticker]),
        _safe_finnhub_quote(db, ticker),
    )

    q = quotes.get(ticker, {})
    result = {
        "ticker": ticker,
        "price": q.get("price"),
        "change": q.get("change"),
        "change_pct": q.get("percent_change"),
        "volume": q.get("volume"),
        "open": fh_quote.get("open") if fh_quote else None,
        "high": fh_quote.get("high") if fh_quote else None,
        "low": fh_quote.get("low") if fh_quote else None,
        "prev_close": fh_quote.get("prev_close") if fh_quote else None,
    }
    return result


async def _safe_finnhub_quote(db: AsyncSession, ticker: str) -> dict | None:
    try:
        return await fh_svc.get_quote(db, ticker)
    except Exception:
        return None
