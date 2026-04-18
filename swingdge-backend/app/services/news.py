"""
Marketaux news sentiment service.

Free tier: 100 req/day.
Fetches last 3 articles per ticker, averages sentiment score.
Cached 4h in PostgreSQL to stay well within the 100 req/day limit.

Sentiment score from Marketaux: -1.0 (very negative) to +1.0 (very positive).
We return a simplified label + the raw average score.
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import cache as cache_svc

logger = logging.getLogger(__name__)
settings = get_settings()

_BASE = "https://api.marketaux.com/v1/news/all"
_TIMEOUT = 10.0
_CACHE_TTL = 60 * 60 * 4  # 4 hours

# ── Daily quota tracker ───────────────────────────────────────────────────────

_quota_count: int = 0
_quota_date: str = ""
_DAILY_LIMIT = 100
_WARN_THRESHOLD = 80


def _increment_quota() -> None:
    global _quota_count, _quota_date
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _quota_date != today:
        _quota_count = 0
        _quota_date = today
    _quota_count += 1


def _quota_ok() -> bool:
    """Return False if we've hit 80% of daily limit — skip call, return None."""
    return _quota_count < _WARN_THRESHOLD


def _fmp_to_marketaux_symbol(ticker: str) -> str:
    """Strip .TO suffix for Marketaux (it uses plain TSX symbols like 'SU')."""
    if ticker.endswith(".TO"):
        return ticker[:-3]
    return ticker


# ── Public API ────────────────────────────────────────────────────────────────

async def get_sentiment(db: AsyncSession, ticker: str) -> dict | None:
    """
    Fetch news sentiment for a ticker. Returns:
        {"ticker": str, "score": float, "label": "positive"|"neutral"|"negative", "article_count": int}
    Returns None if no key configured, quota exhausted, or API error.
    Cached 4h.
    """
    if not settings.marketaux_key:
        return None

    cache_key = f"news:sentiment:{ticker.upper()}"
    cached = await cache_svc.cache_get(db, cache_key)
    if cached is not None:
        return cached

    if not _quota_ok():
        logger.warning("Marketaux quota at %d/%d — skipping sentiment for %s", _quota_count, _DAILY_LIMIT, ticker)
        return None

    symbol = _fmp_to_marketaux_symbol(ticker)
    _increment_quota()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_BASE, params={
                "symbols": symbol,
                "filter_entities": "true",
                "language": "en",
                "limit": 3,
                "api_token": settings.marketaux_key,
            })
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Marketaux request failed for %s: %s", ticker, exc)
        return None

    articles = data.get("data", [])
    if not articles:
        result = {"ticker": ticker, "score": 0.0, "label": "neutral", "article_count": 0}
        await cache_svc.cache_set(db, cache_key, result, _CACHE_TTL, provider="marketaux")
        return result

    scores: list[float] = []
    for article in articles:
        # Each article has an entities list; find the one matching our symbol
        for entity in article.get("entities", []):
            if entity.get("symbol", "").upper() == symbol.upper():
                s = entity.get("sentiment_score")
                if s is not None:
                    scores.append(float(s))
                break

    if not scores:
        result = {"ticker": ticker, "score": 0.0, "label": "neutral", "article_count": len(articles)}
    else:
        avg = sum(scores) / len(scores)
        if avg > 0.1:
            label = "positive"
        elif avg < -0.1:
            label = "negative"
        else:
            label = "neutral"
        result = {"ticker": ticker, "score": round(avg, 4), "label": label, "article_count": len(articles)}

    await cache_svc.cache_set(db, cache_key, result, _CACHE_TTL, provider="marketaux")
    return result
