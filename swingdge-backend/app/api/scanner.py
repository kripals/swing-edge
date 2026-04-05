"""
Scanner API endpoints.

POST /api/scanner/run        — run full scan now, persist results, return candidates
GET  /api/scanner/results    — latest scan results (today)
GET  /api/scanner/history    — past scan result dates + counts
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.auth import verify_token
from app.models.scan_result import ScanResult
from app.services import scanner as scanner_svc
from app.services import trade_plan as tp_svc

router = APIRouter(prefix="/api/scanner", tags=["scanner"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ScanCandidateOut(BaseModel):
    ticker: str
    exchange: str
    sector: str | None
    current_price: float | None
    signal_type: str
    signal_strength: float
    signals: list[str]
    rsi_14: float | None
    macd_histogram: float | None
    volume_ratio: float | None
    above_sma_50: bool
    atr_14: float | None
    relative_strength: float | None
    earnings_date: date | None
    earnings_days_away: int | None
    notes: str

    class Config:
        from_attributes = True


class ScanRunResponse(BaseModel):
    scan_date: date
    candidates_found: int
    candidates: list[ScanCandidateOut]
    duration_ms: int


class ScanResultOut(BaseModel):
    id: int
    ticker: str
    exchange: str | None
    sector: str | None
    current_price: float | None
    signal_type: str
    signal_strength: float | None
    rsi_14: float | None
    volume_ratio: float | None
    above_sma_50: bool | None
    has_trade_plan: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ScanHistoryEntry(BaseModel):
    scan_date: date
    count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run", response_model=ScanRunResponse)
async def run_scan(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Run a full market scan. Persists results to scan_results table.
    Returns all candidates sorted by signal strength desc.
    """
    import time
    start = time.monotonic()

    candidates = await scanner_svc.run_scan(db)

    # Persist to DB
    today = date.today()
    for c in candidates:
        row = ScanResult(
            scan_date=today,
            ticker=c.ticker,
            exchange=c.exchange,
            sector=c.sector,
            current_price=c.current_price,
            signal_type=c.signal_type,
            signal_strength=c.signal_strength,
            rsi_14=c.rsi_14,
            macd_histogram=c.macd_histogram,
            volume_ratio=c.volume_ratio,
            above_sma_50=c.above_sma_50,
            atr_14=c.atr_14,
            relative_strength=c.relative_strength,
            notes=c.notes,
        )
        db.add(row)
    await db.commit()

    duration_ms = int((time.monotonic() - start) * 1000)

    return ScanRunResponse(
        scan_date=today,
        candidates_found=len(candidates),
        candidates=[ScanCandidateOut(**c.__dict__) for c in candidates],
        duration_ms=duration_ms,
    )


@router.get("/results", response_model=list[ScanResultOut])
async def get_results(
    scan_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Return scan results for a given date (defaults to today)."""
    d = scan_date or date.today()
    result = await db.execute(
        select(ScanResult)
        .where(ScanResult.scan_date == d)
        .order_by(desc(ScanResult.signal_strength))
    )
    rows = result.scalars().all()
    return rows


@router.get("/history", response_model=list[ScanHistoryEntry])
async def get_history(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Return list of dates that have scan results, with candidate count."""
    result = await db.execute(
        select(ScanResult.scan_date, func.count(ScanResult.id).label("count"))
        .group_by(ScanResult.scan_date)
        .order_by(desc(ScanResult.scan_date))
        .limit(30)
    )
    rows = result.all()
    return [ScanHistoryEntry(scan_date=r.scan_date, count=r.count) for r in rows]
