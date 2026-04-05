"""
Trade plan API endpoints.

GET  /api/trades/plans                    — list all plans (filterable by status)
GET  /api/trades/plans/:id                — single plan detail
POST /api/trades/plans/generate/:ticker   — generate + return (don't save)
POST /api/trades/plans                    — generate + save
PATCH /api/trades/plans/:id/status        — update lifecycle status
PATCH /api/trades/plans/:id               — update notes
DELETE /api/trades/plans/:id              — soft delete (set status=cancelled)
GET  /api/trades/history                  — closed/stopped/expired plans
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.auth import verify_token
from app.models.trade_plan import TradePlan
from app.services import trade_plan as tp_svc

router = APIRouter(prefix="/api/trades", tags=["trades"])

PlanStatus = Literal["pending", "active", "hit_t1", "hit_t2", "stopped", "expired", "cancelled"]


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TradePlanOut(BaseModel):
    id: int
    ticker: str
    exchange: str
    currency: str
    sector: str | None
    current_price: float
    entry_low: float
    entry_high: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward_ratio: float
    position_size_dollars: float
    position_size_shares: float
    risk_amount: float
    fx_cost_pct: float
    net_gain_after_fx: float | None
    earnings_date: date | None
    earnings_days_away: int | None
    signal_type: str | None
    signal_score: float | None
    status: str
    notes: str | None
    created_at: datetime
    expires_at: datetime | None
    closed_at: datetime | None
    closed_price: float | None
    actual_pnl: float | None

    class Config:
        from_attributes = True


class TradePlanPreview(BaseModel):
    """Returned by generate endpoint — includes violations, not persisted."""
    ticker: str
    exchange: str
    currency: str
    sector: str | None
    current_price: float
    entry_low: float
    entry_high: float
    entry_mid: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward_ratio: float
    position_size_dollars: float
    position_size_shares: float
    risk_amount: float
    fx_cost_pct: float
    net_gain_after_fx: float | None
    fx_warning: bool
    earnings_date: date | None
    earnings_days_away: int | None
    signal_type: str | None
    signal_score: float | None
    violations: list[str]


class CreateTradePlanBody(BaseModel):
    ticker: str
    signal_type: str | None = None
    signal_score: float | None = None
    account_value_cad: float = 7000.0


class PatchStatusBody(BaseModel):
    status: PlanStatus
    closed_price: float | None = None
    actual_pnl: float | None = None
    notes: str | None = None


class PatchNotesBody(BaseModel):
    notes: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/plans", response_model=list[TradePlanOut])
async def list_plans(
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """List trade plans. Filter by status (e.g. ?status=pending)."""
    q = select(TradePlan).order_by(desc(TradePlan.created_at))
    if status_filter:
        q = q.where(TradePlan.status == status_filter)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/plans/{plan_id}", response_model=TradePlanOut)
async def get_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    row = await db.get(TradePlan, plan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trade plan not found")
    return row


@router.get("/plans/generate/{ticker}", response_model=TradePlanPreview)
async def generate_plan(
    ticker: str,
    account_value_cad: float = Query(7000.0),
    signal_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Generate a trade plan preview without saving it."""
    ticker = ticker.upper()
    try:
        plan = await tp_svc.generate(
            db, ticker,
            signal_type=signal_type,
            account_value_cad=account_value_cad,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return TradePlanPreview(**plan.__dict__)


@router.post("/plans", response_model=TradePlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: CreateTradePlanBody,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Generate a trade plan and save it to the database."""
    try:
        plan = await tp_svc.generate(
            db, body.ticker.upper(),
            signal_type=body.signal_type,
            signal_score=body.signal_score,
            account_value_cad=body.account_value_cad,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    row = await tp_svc.save_plan(db, plan)
    return row


@router.patch("/plans/{plan_id}/status", response_model=TradePlanOut)
async def update_status(
    plan_id: int,
    body: PatchStatusBody,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Update a trade plan's lifecycle status."""
    row = await db.get(TradePlan, plan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trade plan not found")

    row.status = body.status
    if body.notes:
        row.notes = body.notes
    if body.closed_price is not None:
        row.closed_price = body.closed_price
        row.closed_at = datetime.utcnow()
    if body.actual_pnl is not None:
        row.actual_pnl = body.actual_pnl

    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/plans/{plan_id}", response_model=TradePlanOut)
async def update_notes(
    plan_id: int,
    body: PatchNotesBody,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    row = await db.get(TradePlan, plan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trade plan not found")
    row.notes = body.notes
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    row = await db.get(TradePlan, plan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trade plan not found")
    row.status = "cancelled"
    await db.commit()


@router.get("/history", response_model=list[TradePlanOut])
async def get_history(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Return closed/stopped/expired/cancelled plans."""
    result = await db.execute(
        select(TradePlan)
        .where(TradePlan.status.in_(["hit_t2", "stopped", "expired", "cancelled"]))
        .order_by(desc(TradePlan.created_at))
        .limit(100)
    )
    return result.scalars().all()
