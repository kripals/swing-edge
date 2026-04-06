"""
Bank of Canada Valet API client.

Free, no API key required. Rate limits are generous.
Used for macro context in trade plans and the Market view.

Series used:
  V39079    — Bank Rate (overnight target rate)
  FXUSDCAD  — USD/CAD spot rate
  V41690973 — CPI All-items Canada (monthly)

Valet API docs: https://www.bankofcanada.ca/valet/docs
"""
from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import cache as cache_svc

_BASE = "https://www.bankofcanada.ca/valet"
_TIMEOUT = 10.0


async def _get_latest(series: str) -> dict[str, Any] | None:
    """Fetch the most recent observation for a BoC series."""
    url = f"{_BASE}/observations/{series}/json"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params={"recent": 1})
        resp.raise_for_status()
        data = resp.json()

    observations = data.get("observations", [])
    if not observations:
        return None
    return observations[-1]  # most recent


async def get_overnight_rate(db: AsyncSession) -> dict | None:
    """
    Bank of Canada overnight target rate.
    Returns {value: float, date: str} or None.
    Cached 24h.
    """
    key = "boc:overnight_rate"
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        return cached

    obs = await _get_latest("V39079")
    if obs is None:
        return None

    result = {
        "value": float(obs["V39079"]["v"]),
        "date": obs["d"],
        "label": "Overnight Rate",
        "unit": "%",
    }
    await cache_svc.cache_set(db, key, result, cache_svc.TTL.MACRO, provider="boc")
    return result


async def get_usd_cad(db: AsyncSession) -> dict | None:
    """
    USD/CAD spot rate from BoC.
    Returns {value: float, date: str} or None.
    Cached 24h.
    """
    key = "boc:usd_cad"
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        return cached

    obs = await _get_latest("FXUSDCAD")
    if obs is None:
        return None

    result = {
        "value": float(obs["FXUSDCAD"]["v"]),
        "date": obs["d"],
        "label": "USD/CAD",
        "unit": "CAD",
    }
    await cache_svc.cache_set(db, key, result, cache_svc.TTL.MACRO, provider="boc")
    return result


async def get_cpi(db: AsyncSession) -> dict | None:
    """
    CPI All-items Canada (monthly, year-over-year is computed externally).
    Returns {value: float, date: str} or None.
    Cached 24h.
    """
    key = "boc:cpi"
    cached = await cache_svc.cache_get(db, key)
    if cached is not None:
        return cached

    obs = await _get_latest("V41690973")
    if obs is None:
        return None

    result = {
        "value": float(obs["V41690973"]["v"]),
        "date": obs["d"],
        "label": "CPI (Canada)",
        "unit": "index",
    }
    await cache_svc.cache_set(db, key, result, cache_svc.TTL.MACRO, provider="boc")
    return result
