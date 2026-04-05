"""
Two-layer cache:
  Layer 1 — in-memory dict (hot data during market hours, lost on Render sleep)
  Layer 2 — PostgreSQL api_cache table (survives restarts + Render sleep cycles)

TTL strategy (from architecture v3 section 4):
  - Intraday quotes:      1-5 min (in-memory only)
  - Daily OHLCV:          18-24 h
  - Technical indicators: 18-24 h
  - Fundamentals:         24-72 h
  - Company profiles:     7-30 days
  - News:                 15-30 min
  - Commodities:          5-15 min
  - BoC / macro:          24 h
  - Earnings dates:       24 h
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ── TTL presets (seconds) ─────────────────────────────────────────────────────

class TTL:
    INTRADAY_QUOTE  = 120          # 2 min — in-memory only
    COMMODITY       = 600          # 10 min
    NEWS            = 900          # 15 min
    DAILY_OHLCV     = 60 * 60 * 20 # 20 h
    INDICATORS      = 60 * 60 * 20 # 20 h
    EARNINGS        = 60 * 60 * 24 # 24 h
    MACRO           = 60 * 60 * 24 # 24 h
    FUNDAMENTALS    = 60 * 60 * 48 # 48 h
    COMPANY_PROFILE = 60 * 60 * 24 * 14  # 14 days


# ── In-memory layer ───────────────────────────────────────────────────────────

_memory_cache: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at_unix)


def _mem_get(key: str) -> Any | None:
    entry = _memory_cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.time() > expires_at:
        del _memory_cache[key]
        return None
    return value


def _mem_set(key: str, value: Any, ttl_seconds: int) -> None:
    _memory_cache[key] = (value, time.time() + ttl_seconds)


def _mem_delete(key: str) -> None:
    _memory_cache.pop(key, None)


def mem_cache_size() -> int:
    return len(_memory_cache)


# ── PostgreSQL layer ──────────────────────────────────────────────────────────

async def _pg_get(db: AsyncSession, key: str) -> Any | None:
    result = await db.execute(
        text("SELECT cache_value FROM api_cache WHERE cache_key = :key AND expires_at > NOW()"),
        {"key": key},
    )
    row = result.fetchone()
    return row[0] if row else None


async def _pg_set(db: AsyncSession, key: str, value: Any, ttl_seconds: int, provider: str | None = None) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    await db.execute(
        text("""
            INSERT INTO api_cache (cache_key, cache_value, provider, expires_at)
            VALUES (:key, :value::jsonb, :provider, :expires_at)
            ON CONFLICT (cache_key) DO UPDATE
                SET cache_value = EXCLUDED.cache_value,
                    expires_at  = EXCLUDED.expires_at,
                    created_at  = NOW()
        """),
        {"key": key, "value": json.dumps(value), "provider": provider, "expires_at": expires_at},
    )


async def _pg_delete(db: AsyncSession, key: str) -> None:
    await db.execute(text("DELETE FROM api_cache WHERE cache_key = :key"), {"key": key})


# ── Public interface ──────────────────────────────────────────────────────────

async def cache_get(
    db: AsyncSession,
    key: str,
    memory_only: bool = False,
) -> Any | None:
    """Get from in-memory first, fall back to PostgreSQL."""
    value = _mem_get(key)
    if value is not None:
        return value
    if memory_only:
        return None
    return await _pg_get(db, key)


async def cache_set(
    db: AsyncSession,
    key: str,
    value: Any,
    ttl_seconds: int,
    provider: str | None = None,
    memory_only: bool = False,
) -> None:
    """Write to in-memory. If not memory_only, also persist to PostgreSQL."""
    _mem_set(key, value, ttl_seconds)
    if not memory_only:
        await _pg_set(db, key, value, ttl_seconds, provider)


async def cache_delete(db: AsyncSession, key: str) -> None:
    _mem_delete(key)
    await _pg_delete(db, key)


async def cache_cleanup(db: AsyncSession) -> int:
    """Remove expired rows from PostgreSQL cache table. Returns number deleted."""
    result = await db.execute(text("DELETE FROM api_cache WHERE expires_at <= NOW()"))
    await db.commit()
    return result.rowcount


# ── Convenience key builders ──────────────────────────────────────────────────

def quote_key(ticker: str) -> str:
    return f"quote:{ticker.upper()}"

def ohlcv_key(ticker: str, interval: str = "1day") -> str:
    return f"ohlcv:{ticker.upper()}:{interval}"

def indicators_key(ticker: str) -> str:
    return f"indicators:{ticker.upper()}"

def earnings_key(ticker: str) -> str:
    return f"earnings:{ticker.upper()}"

def fundamentals_key(ticker: str) -> str:
    return f"fundamentals:{ticker.upper()}"

def macro_key(series: str) -> str:
    return f"macro:{series}"

def commodity_key(symbol: str) -> str:
    return f"commodity:{symbol.upper()}"
