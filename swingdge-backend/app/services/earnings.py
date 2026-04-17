"""
Earnings date checker — FMP primary, Finnhub fallback.

Returns the next earnings date for a ticker and whether the ticker is
inside the 5-day blackout window (configurable via trading_rules).

FMP endpoint: GET /v3/earning_calendar?symbol=AAPL&apikey=...
  Returns a list sorted by date. We grab the first future date.

Finnhub endpoint: GET /calendar/earnings?symbol=AAPL&token=...
  Returns earningsCalendar list.

Results are cached 24h in the PostgreSQL cache table since earnings
dates don't change intraday.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import cache as cache_svc
from app.services import fmp as fmp_svc
from app.services import rules as rules_svc

settings = get_settings()

_FINNHUB_BASE = "https://finnhub.io/api/v1"
_TIMEOUT = 10.0


def _cache_key(ticker: str) -> str:
    return f"earnings:{ticker}"


async def get_next_earnings_date(db: AsyncSession, ticker: str) -> date | None:
    """
    Return next earnings date for ticker, or None if unknown.
    Cached 24h.
    """
    key = _cache_key(ticker)
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        raw = cached.get("date")
        return date.fromisoformat(raw) if raw else None

    result = await _fetch_fmp(ticker) or await _fetch_finnhub(ticker)

    # Cache even if None (store {"date": null}) to avoid hammering APIs
    await cache_svc.cache_set(
        db, key,
        {"date": result.isoformat() if result else None},
        cache_svc.TTL.DAILY_OHLCV,   # 20h TTL — good enough for earnings
        provider="fmp",
    )
    return result


async def _fetch_fmp(ticker: str) -> date | None:
    try:
        today = date.today().isoformat()
        # Route through fmp_svc._get() so the quota counter is incremented
        data = await fmp_svc._get(f"earning_calendar", {"symbol": ticker})
        if not isinstance(data, list):
            return None
        for row in data:
            d = row.get("date", "")
            if d >= today:
                return date.fromisoformat(d)
    except Exception:
        pass
    return None


async def _fetch_finnhub(ticker: str) -> date | None:
    try:
        today = date.today()
        from_str = today.isoformat()
        # Look 90 days ahead
        from datetime import timedelta
        to_str = (today + timedelta(days=90)).isoformat()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_FINNHUB_BASE}/calendar/earnings",
                params={"symbol": ticker, "from": from_str, "to": to_str, "token": settings.finnhub_key},
            )
            resp.raise_for_status()
            data = resp.json()
            for row in (data.get("earningsCalendar") or []):
                d = row.get("date", "")
                if d >= from_str:
                    return date.fromisoformat(d)
    except Exception:
        pass
    return None


async def is_in_blackout(
    db: AsyncSession,
    ticker: str,
    earnings_date: date | None = None,
) -> tuple[bool, date | None, int | None]:
    """
    Returns (in_blackout, earnings_date, days_away).
    in_blackout=True means the scanner should skip this ticker.
    """
    if earnings_date is None:
        earnings_date = await get_next_earnings_date(db, ticker)

    if earnings_date is None:
        return False, None, None

    blackout = await rules_svc.earnings_blackout_days(db)
    today = date.today()
    days_away = (earnings_date - today).days

    if days_away < 0:
        # Past earnings — not in blackout
        return False, earnings_date, days_away

    in_blackout = days_away <= blackout
    return in_blackout, earnings_date, days_away
