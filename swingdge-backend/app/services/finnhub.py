"""
Finnhub client — earnings calendar, real-time quotes, company news.

Free tier: 60 requests/minute — generous.
Primary uses:
  - Earnings dates (critical for blackout enforcement)
  - Supplemental real-time quotes
  - Company news
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import cache as cache_svc

settings = get_settings()

_BASE = "https://finnhub.io/api/v1"
_TIMEOUT = 10.0


async def _get(endpoint: str, params: dict[str, Any]) -> Any:
    params["token"] = settings.finnhub_key
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_BASE}/{endpoint}", params=params)
        resp.raise_for_status()
        return resp.json()


def _finnhub_symbol(ticker: str) -> str:
    """Convert 'SU.TO' → 'SU.TO' (Finnhub uses .TO suffix natively for TSX)."""
    return ticker


# ── Earnings ──────────────────────────────────────────────────────────────────

async def get_next_earnings(db: AsyncSession, ticker: str) -> dict | None:
    """
    Returns the next upcoming earnings event: {date, eps_estimate, revenue_estimate, ...}
    Cached 24h. Returns None if no upcoming earnings found.
    """
    key = cache_svc.earnings_key(ticker)
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        return cached if cached else None

    symbol = _finnhub_symbol(ticker)
    today = date.today()
    look_ahead = today + timedelta(days=90)

    data = await _get("calendar/earnings", {
        "symbol": symbol,
        "from": today.isoformat(),
        "to": look_ahead.isoformat(),
    })

    earnings_list = data.get("earningsCalendar", [])
    if not earnings_list:
        await cache_svc.cache_set(db, key, {}, cache_svc.TTL.EARNINGS, provider="finnhub")
        return None

    # Sort by date and take the nearest
    upcoming = sorted(earnings_list, key=lambda e: e.get("date", ""))
    next_event = upcoming[0]

    result = {
        "date": next_event.get("date"),
        "eps_estimate": next_event.get("epsEstimate"),
        "revenue_estimate": next_event.get("revenueEstimate"),
        "quarter": next_event.get("quarter"),
        "year": next_event.get("year"),
    }

    await cache_svc.cache_set(db, key, result, cache_svc.TTL.EARNINGS, provider="finnhub")
    return result


async def get_earnings_days_away(db: AsyncSession, ticker: str) -> int | None:
    """
    Returns number of calendar days until next earnings, or None if not found.
    Used by the earnings blackout rule.
    """
    earnings = await get_next_earnings(db, ticker)
    if not earnings or not earnings.get("date"):
        return None
    try:
        earnings_date = date.fromisoformat(earnings["date"])
        delta = (earnings_date - date.today()).days
        return max(delta, 0)
    except (ValueError, TypeError):
        return None


# ── Quotes ────────────────────────────────────────────────────────────────────

async def get_quote(db: AsyncSession, ticker: str) -> dict | None:
    """
    Real-time quote from Finnhub. Used as supplement to Twelve Data.
    Returns {price, open, high, low, prev_close, change, change_pct, timestamp}
    """
    key = cache_svc.quote_key(f"fh:{ticker}")
    cached = cache_svc._mem_get(key)
    if cached:
        return cached

    symbol = _finnhub_symbol(ticker)
    data = await _get("quote", {"symbol": symbol})

    if not data or data.get("c") == 0:
        return None

    quote = {
        "ticker": ticker,
        "price": data.get("c"),           # current price
        "open": data.get("o"),
        "high": data.get("h"),
        "low": data.get("l"),
        "prev_close": data.get("pc"),
        "change": data.get("d"),
        "change_pct": data.get("dp"),
        "timestamp": data.get("t"),
    }

    cache_svc._mem_set(key, quote, cache_svc.TTL.INTRADAY_QUOTE)
    return quote


# ── News ──────────────────────────────────────────────────────────────────────

async def get_company_news(db: AsyncSession, ticker: str, days: int = 7) -> list[dict]:
    """
    Fetch recent company news. Used for confirmation/avoidance context in trade plans.
    Cached 15 min.
    """
    key = f"news:{ticker.upper()}"
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        return cached

    symbol = _finnhub_symbol(ticker)
    today = date.today()
    from_date = (today - timedelta(days=days)).isoformat()

    data = await _get("company-news", {
        "symbol": symbol,
        "from": from_date,
        "to": today.isoformat(),
    })

    if not isinstance(data, list):
        return []

    articles = [
        {
            "headline": item.get("headline"),
            "summary": item.get("summary"),
            "source": item.get("source"),
            "url": item.get("url"),
            "datetime": item.get("datetime"),
        }
        for item in data[:10]  # Cap at 10 articles
    ]

    await cache_svc.cache_set(db, key, articles, cache_svc.TTL.NEWS, provider="finnhub")
    return articles
