"""
Alpha Vantage client — backup price data + commodity prices.

Free tier: 25 API calls/day — use sparingly.
Primary use: WTI oil, gold, natural gas, copper.
Backup use: price data when Twelve Data is exhausted.

Rate limiting: enforced by this module to prevent accidental daily limit burn.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import cache as cache_svc

settings = get_settings()

_BASE = "https://www.alphavantage.co/query"
_TIMEOUT = 15.0

# Daily call counter — resets at midnight UTC
_call_count: int = 0
_call_count_date: str = ""
_DAILY_LIMIT = 25


def _check_daily_limit() -> None:
    global _call_count, _call_count_date
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _call_count_date != today:
        _call_count = 0
        _call_count_date = today
    if _call_count >= _DAILY_LIMIT:
        raise RuntimeError(f"Alpha Vantage daily limit reached ({_DAILY_LIMIT} calls/day)")
    _call_count += 1


async def _get(params: dict[str, Any]) -> dict[str, Any]:
    _check_daily_limit()
    params["apikey"] = settings.alpha_vantage_key
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()
        if "Error Message" in data:
            raise ValueError(f"Alpha Vantage error: {data['Error Message']}")
        if "Note" in data:
            # Rate limit warning — treat as soft failure
            raise RuntimeError(f"Alpha Vantage rate limit: {data['Note']}")
        return data


# ── Commodity Prices ──────────────────────────────────────────────────────────

async def get_commodity(db: AsyncSession, symbol: str) -> float | None:
    """
    Fetch latest commodity price. symbol ∈ {WTI, BRENT, NATURAL_GAS, COPPER, ALUMINUM}
    Cached 10 min (commodities are volatile but we have only 25 calls/day).
    """
    key = cache_svc.commodity_key(symbol)
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        return cached

    data = await _get({"function": "BRENT" if symbol == "BRENT" else symbol})
    # AV returns {"data": [{"date": "...", "value": "..."}, ...]}
    records = data.get("data", [])
    if not records:
        return None
    latest = records[0].get("value")
    price = float(latest) if latest and latest != "." else None

    if price is not None:
        await cache_svc.cache_set(db, key, price, cache_svc.TTL.COMMODITY, provider="alpha_vantage")
    return price


async def get_wti_oil(db: AsyncSession) -> float | None:
    return await get_commodity(db, "WTI")


async def get_gold(db: AsyncSession) -> float | None:
    """Gold via Alpha Vantage FX endpoint (XAU/USD)."""
    key = cache_svc.commodity_key("GOLD")
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        return cached

    data = await _get({"function": "CURRENCY_EXCHANGE_RATE", "from_currency": "XAU", "to_currency": "USD"})
    rate_info = data.get("Realtime Currency Exchange Rate", {})
    price_str = rate_info.get("5. Exchange Rate")
    price = float(price_str) if price_str else None

    if price is not None:
        await cache_svc.cache_set(db, key, price, cache_svc.TTL.COMMODITY, provider="alpha_vantage")
    return price


async def get_natural_gas(db: AsyncSession) -> float | None:
    return await get_commodity(db, "NATURAL_GAS")


async def get_copper(db: AsyncSession) -> float | None:
    return await get_commodity(db, "COPPER")


# ── Backup Price Data ─────────────────────────────────────────────────────────

async def get_quote_backup(db: AsyncSession, ticker: str) -> float | None:
    """
    Fallback quote when Twelve Data is down. Costs 1 of 25 daily calls — use only when needed.
    TSX tickers: append .TRT (Alpha Vantage TSX suffix) or use .TO
    """
    key = cache_svc.quote_key(f"av:{ticker}")
    cached = await cache_svc.cache_get(db, key, memory_only=True)
    if cached:
        return cached.get("price")

    data = await _get({"function": "GLOBAL_QUOTE", "symbol": ticker})
    quote = data.get("Global Quote", {})
    price_str = quote.get("05. price")
    price = float(price_str) if price_str else None

    if price is not None:
        cache_svc._mem_set(key, {"price": price}, cache_svc.TTL.INTRADAY_QUOTE)
    return price
