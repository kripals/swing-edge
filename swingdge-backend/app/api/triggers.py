"""
Trigger endpoints — called by GitHub Actions cron workflows.
All require Authorization: Bearer <TRIGGER_SECRET> header.

These are the entry points for all scheduled jobs:
  morning-scan    → run full scanner pipeline
  price-check     → check active trades vs entry/stop/target
  daily-summary   → send Telegram daily summary
  macro-update    → update BoC rate, commodities, USD/CAD
  earnings-check  → flag holdings with earnings this week
  portfolio-sync  → SnapTrade sync
  sector-update   → sector rotation calculations
  cache-cleanup   → purge expired cache rows
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.auth import verify_trigger_secret
from app.services import cache as cache_svc

router = APIRouter(prefix="/api/trigger", tags=["triggers"])


class TriggerResult(BaseModel):
    job: str
    status: str
    message: str
    triggered_at: str
    duration_ms: int | None = None


async def _run_timed(job_name: str, coro) -> TriggerResult:
    start = datetime.now(timezone.utc)
    try:
        message = await coro
        duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        return TriggerResult(
            job=job_name,
            status="ok",
            message=message or "done",
            triggered_at=start.isoformat(),
            duration_ms=duration,
        )
    except Exception as exc:
        duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        return TriggerResult(
            job=job_name,
            status="error",
            message=str(exc),
            triggered_at=start.isoformat(),
            duration_ms=duration,
        )


# ── Trigger endpoints ─────────────────────────────────────────────────────────

@router.post("/morning-scan")
async def trigger_morning_scan(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        # Phase 2: scanner_engine will be wired here
        return "Morning scan not yet implemented — Phase 2"

    return await _run_timed("morning-scan", _job())


@router.post("/price-check")
async def trigger_price_check(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        # Phase 4: price monitor will be wired here
        return "Price check not yet implemented — Phase 4"

    return await _run_timed("price-check", _job())


@router.post("/daily-summary")
async def trigger_daily_summary(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        # Phase 4: notification_service will be wired here
        return "Daily summary not yet implemented — Phase 4"

    return await _run_timed("daily-summary", _job())


@router.post("/macro-update")
async def trigger_macro_update(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        # Phase 3: macro_tracker will be wired here
        return "Macro update not yet implemented — Phase 3"

    return await _run_timed("macro-update", _job())


@router.post("/earnings-check")
async def trigger_earnings_check(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        return "Earnings check not yet implemented — Phase 2"

    return await _run_timed("earnings-check", _job())


@router.post("/portfolio-sync")
async def trigger_portfolio_sync(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import snaptrade
        result = await snaptrade.sync_portfolio(db)
        return f"Synced {result['accounts_updated']} accounts, {result['positions_updated']} positions"

    return await _run_timed("portfolio-sync", _job())


@router.post("/sector-update")
async def trigger_sector_update(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        return "Sector update not yet implemented — Phase 3"

    return await _run_timed("sector-update", _job())


@router.post("/cache-cleanup")
async def trigger_cache_cleanup(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        deleted = await cache_svc.cache_cleanup(db)
        return f"Removed {deleted} expired cache entries"

    return await _run_timed("cache-cleanup", _job())
