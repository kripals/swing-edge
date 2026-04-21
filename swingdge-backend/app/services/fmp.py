"""
Financial Modeling Prep (FMP) client — fundamentals + analyst ratings.

Free tier: 250 req/day.
Primary uses:
  - Company profile (P/E, EPS, market cap, sector, beta)
  - Analyst stock recommendations (buy/hold/sell consensus)
  - Earnings surprises (historical EPS vs estimate)

FMP docs: https://financialmodelingprep.com/developer/docs
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import cache as cache_svc

settings = get_settings()
logger = logging.getLogger(__name__)

_BASE = "https://financialmodelingprep.com/api/v3"
_TIMEOUT = 10.0

# ── Daily quota tracker ───────────────────────────────────────────────────────

_quota_count: int = 0
_quota_date: str = ""
_DAILY_LIMIT = 250
_WARN_THRESHOLD = 200  # 80% of daily limit


def _increment_quota() -> None:
    """Increment daily call counter, resetting at midnight UTC."""
    global _quota_count, _quota_date
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _quota_date != today:
        _quota_count = 0
        _quota_date = today
    _quota_count += 1


async def _check_quota_warning() -> None:
    """Send a Telegram warning once when usage crosses 80% of daily limit."""
    if _quota_count == _WARN_THRESHOLD:
        import logging
        logging.getLogger(__name__).warning(
            "FMP quota at %d/%d (80%%) — approaching daily limit", _quota_count, _DAILY_LIMIT
        )
        try:
            from app.services import telegram as tg
            await tg.send_message(
                f"⚠️ <b>FMP quota warning</b>\n"
                f"Used {_quota_count}/{_DAILY_LIMIT} requests today (80%).\n"
                f"Earnings and fundamentals data may stop updating."
            )
        except Exception:
            pass


def _fmp_symbol(ticker: str) -> str:
    """Convert 'SU.TO' → 'SU.TO' (FMP accepts .TO natively for TSX)."""
    return ticker


async def _get(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    _increment_quota()
    await _check_quota_warning()
    p = {"apikey": settings.fmp_key}
    if params:
        p.update(params)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_BASE}/{endpoint}", params=p)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "Error Message" in data:
            raise ValueError(f"FMP error: {data['Error Message']}")
        return data


# ── Company profile ───────────────────────────────────────────────────────────

async def get_profile(db: AsyncSession, ticker: str) -> dict | None:
    """
    Fetch company profile: sector, industry, P/E, EPS, beta, market cap, description.
    Cached 48h.
    """
    key = f"fmp:profile:{ticker.upper()}"
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        return cached

    symbol = _fmp_symbol(ticker)
    data = await _get(f"profile/{symbol}")

    if not data or not isinstance(data, list):
        return None

    raw = data[0]
    result = {
        "ticker": ticker,
        "name": raw.get("companyName"),
        "sector": raw.get("sector"),
        "industry": raw.get("industry"),
        "description": raw.get("description"),
        "pe_ratio": raw.get("pe"),
        "eps": raw.get("eps"),
        "beta": raw.get("beta"),
        "market_cap": raw.get("mktCap"),
        "dividend_yield": raw.get("lastDiv"),
        "52w_high": raw.get("range", "").split("-")[-1].strip() if raw.get("range") else None,
        "52w_low": raw.get("range", "").split("-")[0].strip() if raw.get("range") else None,
        "avg_volume": raw.get("volAvg"),
        "exchange": raw.get("exchangeShortName"),
        "currency": raw.get("currency"),
        "website": raw.get("website"),
    }

    await cache_svc.cache_set(db, key, result, cache_svc.TTL.FUNDAMENTALS, provider="fmp")
    return result


# ── Analyst recommendations ───────────────────────────────────────────────────

async def get_analyst_ratings(db: AsyncSession, ticker: str) -> dict | None:
    """
    Latest analyst consensus: strongBuy, buy, hold, sell, strongSell counts.
    Cached 48h.
    """
    key = f"fmp:analyst:{ticker.upper()}"
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        return cached

    symbol = _fmp_symbol(ticker)
    data = await _get(f"analyst-stock-recommendations/{symbol}", {"limit": 1})

    if not data or not isinstance(data, list):
        return None

    raw = data[0]
    strong_buy = raw.get("analystRatingsStrongBuy", 0) or 0
    buy = raw.get("analystRatingsBuy", 0) or 0
    hold = raw.get("analystRatingsHold", 0) or 0
    sell = raw.get("analystRatingsSell", 0) or 0
    strong_sell = raw.get("analystRatingsStrongSell", 0) or 0
    total = strong_buy + buy + hold + sell + strong_sell

    consensus = "N/A"
    if total > 0:
        bullish = strong_buy + buy
        bearish = sell + strong_sell
        if bullish / total >= 0.6:
            consensus = "Buy"
        elif bearish / total >= 0.4:
            consensus = "Sell"
        else:
            consensus = "Hold"

    result = {
        "ticker": ticker,
        "date": raw.get("date"),
        "consensus": consensus,
        "strong_buy": strong_buy,
        "buy": buy,
        "hold": hold,
        "sell": sell,
        "strong_sell": strong_sell,
        "total": total,
    }

    await cache_svc.cache_set(db, key, result, cache_svc.TTL.FUNDAMENTALS, provider="fmp")
    return result


# ── Earnings surprises ────────────────────────────────────────────────────────

async def get_tsx_screener(
    _db: AsyncSession,
    min_mktcap: int = 2_000_000_000,
    min_volume: int = 200_000,
    limit: int = 100,
) -> list[dict]:
    """
    Fetch TSX-listed stocks via yfinance EquityQuery screener.
    Filters: exchange=TOR, market cap > $2B, avg 3-month volume > 200K.
    No API key required. Called weekly by ticker-discovery trigger.
    """
    import asyncio

    def _fetch() -> list[dict]:
        import yfinance as yf
        from yfinance import EquityQuery

        try:
            q = EquityQuery("and", [
                EquityQuery("eq", ["exchange", "TOR"]),
                EquityQuery("gt", ["intradaymarketcap", min_mktcap]),
            ])
            result = yf.screen(q, sortField="intradaymarketcap", sortAsc=False, count=200)
            quotes = result.get("quotes", []) if isinstance(result, dict) else []
        except Exception as e:
            logger.warning("yfinance TSX screener failed: %s", e)
            return []

        results = []
        for item in quotes:
            symbol = item.get("symbol", "")
            if not symbol.endswith(".TO"):
                continue
            volume = item.get("averageDailyVolume3Month") or item.get("regularMarketVolume") or 0
            if volume < min_volume:
                continue
            results.append({
                "ticker": symbol,
                "name": item.get("shortName") or item.get("longName"),
                "sector": item.get("sector"),
                "exchange": "TSX",
                "market_cap": item.get("marketCap") or 0,
                "avg_volume": volume,
                "currency": "CAD",
            })
            if len(results) >= limit:
                break

        return results

    return await asyncio.get_event_loop().run_in_executor(None, _fetch)


async def get_tsx_gainers(
    _db: AsyncSession,
    min_volume: int = 500_000,
    limit: int = 20,
) -> list[dict]:
    """
    Fetch today's top TSX gainers via yfinance EquityQuery screener.
    Filters: exchange=TOR, price change > 2%, volume > 500K.
    No API key required. Called daily by momentum-watchlist trigger.
    """
    import asyncio

    def _fetch() -> list[dict]:
        import yfinance as yf
        from yfinance import EquityQuery

        try:
            q = EquityQuery("and", [
                EquityQuery("eq", ["exchange", "TOR"]),
                EquityQuery("gt", ["percentchange", 2]),
            ])
            result = yf.screen(q, sortField="percentchange", sortAsc=False, count=100)
            quotes = result.get("quotes", []) if isinstance(result, dict) else []
        except Exception as e:
            logger.warning("yfinance TSX gainers failed: %s", e)
            return []

        results = []
        for item in quotes:
            symbol = item.get("symbol", "")
            if not symbol.endswith(".TO"):
                continue
            volume = item.get("regularMarketVolume") or 0
            if volume < min_volume:
                continue
            results.append({
                "ticker": symbol,
                "name": item.get("shortName") or item.get("longName"),
                "price": item.get("regularMarketPrice"),
                "change_pct": item.get("regularMarketChangePercent"),
                "volume": volume,
                "currency": "CAD",
                "exchange": "TSX",
            })
            if len(results) >= limit:
                break

        return results

    return await asyncio.get_event_loop().run_in_executor(None, _fetch)


async def get_earnings_history(db: AsyncSession, ticker: str, limit: int = 4) -> list[dict]:
    """
    Last N quarters of EPS actuals vs estimates.
    Cached 48h.
    """
    key = f"fmp:earnings_hist:{ticker.upper()}"
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        return cached

    symbol = _fmp_symbol(ticker)
    data = await _get(f"earnings-surprises/{symbol}")

    if not data or not isinstance(data, list):
        return []

    result = [
        {
            "date": item.get("date"),
            "eps_actual": item.get("actualEarningResult"),
            "eps_estimate": item.get("estimatedEarning"),
            "surprise": round(
                (item.get("actualEarningResult", 0) or 0) - (item.get("estimatedEarning", 0) or 0), 4
            ),
        }
        for item in data[:limit]
    ]

    await cache_svc.cache_set(db, key, result, cache_svc.TTL.FUNDAMENTALS, provider="fmp")
    return result
