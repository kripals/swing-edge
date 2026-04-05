"""
Trading rules engine — reads rules from the `trading_rules` table.

Rules are cached in-memory and refreshed every 5 minutes so the scanner
always gets fresh values without hitting the DB on every ticker.

Rule keys match what was seeded in scripts/seed.py.
"""
from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading_rule import TradingRule

# In-memory cache: {rule_key: (value, loaded_at)}
_cache: dict[str, tuple[Any, float]] = {}
_CACHE_TTL = 300  # 5 minutes


def _cast(raw: str, value_type: str) -> Any:
    if value_type == "float" or value_type == "number" or value_type == "percentage":
        return float(raw)
    if value_type == "int" or value_type == "integer":
        return int(raw)
    if value_type == "bool" or value_type == "boolean":
        return raw.lower() in ("true", "1", "yes")
    return raw  # string


async def _load(db: AsyncSession) -> None:
    result = await db.execute(select(TradingRule))
    rows = result.scalars().all()
    now = time.time()
    for row in rows:
        _cache[row.rule_key] = (_cast(row.rule_value, row.value_type), now)


async def get_rule(db: AsyncSession, key: str, default: Any = None) -> Any:
    """Return a typed rule value. Refreshes cache if stale."""
    entry = _cache.get(key)
    if entry is None or time.time() - entry[1] > _CACHE_TTL:
        await _load(db)
        entry = _cache.get(key)
    if entry is None:
        return default
    return entry[0]


async def get_all_rules(db: AsyncSession) -> dict[str, Any]:
    """Return all rules as a flat dict {key: typed_value}."""
    if not _cache or time.time() - next(iter(_cache.values()))[1] > _CACHE_TTL:
        await _load(db)
    return {k: v for k, (v, _) in _cache.items()}


def invalidate_cache() -> None:
    """Force next call to re-read from DB (call after a rule is updated)."""
    _cache.clear()


# ── Convenience getters for the values the scanner/trade plan use ─────────────

async def risk_pct(db: AsyncSession) -> float:
    return await get_rule(db, "risk_per_trade_pct", 1.0)

async def min_rr(db: AsyncSession) -> float:
    return await get_rule(db, "min_risk_reward", 2.0)

async def earnings_blackout_days(db: AsyncSession) -> int:
    return await get_rule(db, "earnings_blackout_days", 5)

async def max_active_trades(db: AsyncSession) -> int:
    return await get_rule(db, "max_active_trades", 5)

async def trade_expiry_days(db: AsyncSession) -> int:
    return await get_rule(db, "trade_expiry_days", 10)

async def min_market_cap(db: AsyncSession) -> float:
    return await get_rule(db, "scanner_min_market_cap", 2_000_000_000)

async def scanner_rsi_oversold(db: AsyncSession) -> int:
    return await get_rule(db, "scanner_rsi_oversold", 30)

async def scanner_rsi_upper(db: AsyncSession) -> int:
    return await get_rule(db, "scanner_rsi_upper_bound", 50)

async def scanner_volume_multiplier(db: AsyncSession) -> float:
    return await get_rule(db, "scanner_volume_multiplier", 1.5)

async def scanner_min_price(db: AsyncSession) -> float:
    return await get_rule(db, "scanner_min_price", 2.0)

async def scanner_min_avg_volume(db: AsyncSession) -> int:
    return await get_rule(db, "scanner_min_avg_volume", 100_000)

async def max_sector_pct(db: AsyncSession) -> float:
    return await get_rule(db, "max_sector_exposure_pct", 30.0)

async def max_position_pct(db: AsyncSession) -> float:
    return await get_rule(db, "max_position_size_pct", 15.0)

async def fx_fee_pct(db: AsyncSession) -> float:
    return await get_rule(db, "fx_fee_per_conversion_pct", 1.5)

async def has_usd_account(db: AsyncSession) -> bool:
    return await get_rule(db, "has_usd_account", False)

async def fx_warning_threshold(db: AsyncSession) -> float:
    return await get_rule(db, "fx_warning_threshold_pct", 3.0)

async def us_trade_min_target_pct(db: AsyncSession) -> float:
    return await get_rule(db, "us_trade_min_target_pct", 8.0)
