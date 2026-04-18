"""
Portfolio Advisor API endpoints.

GET /api/advisor/results — analyze all holdings and return HOLD/WATCH/SELL recommendations.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.auth import verify_token

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


class AdvisorResultSchema(BaseModel):
    ticker: str
    account_name: str
    action: str
    reason: str
    unrealized_pnl_pct: float
    fx_adjusted_pnl_pct: float
    current_price: float | None
    avg_cost: float
    shares: float
    rsi_14: float | None
    sma_50: float | None
    above_sma_50: bool | None
    macd_histogram: float | None
    adx_14: float | None
    volume_ratio: float | None
    atr_14: float | None
    is_leveraged_etf: bool
    has_fx_cost: bool
    currency: str
    earnings_days_away: int | None
    flags: list[str]


class AdvisorResponse(BaseModel):
    results: list[AdvisorResultSchema]
    sell_count: int
    watch_count: int
    hold_count: int
    leveraged_count: int
    run_at: str


@router.get("/results", dependencies=[Depends(verify_token)])
async def get_advisor_results(db: AsyncSession = Depends(get_db)) -> AdvisorResponse:
    from app.services import advisor as advisor_svc

    results = await advisor_svc.analyze_holdings(db)

    return AdvisorResponse(
        results=[
            AdvisorResultSchema(
                ticker=r.ticker,
                account_name=r.account_name,
                action=r.action,
                reason=r.reason,
                unrealized_pnl_pct=r.unrealized_pnl_pct,
                fx_adjusted_pnl_pct=r.fx_adjusted_pnl_pct,
                current_price=r.current_price,
                avg_cost=r.avg_cost,
                shares=r.shares,
                rsi_14=r.rsi_14,
                sma_50=r.sma_50,
                above_sma_50=r.above_sma_50,
                macd_histogram=r.macd_histogram,
                adx_14=r.adx_14,
                volume_ratio=r.volume_ratio,
                atr_14=r.atr_14,
                is_leveraged_etf=r.is_leveraged_etf,
                has_fx_cost=r.has_fx_cost,
                currency=r.currency,
                earnings_days_away=r.earnings_days_away,
                flags=r.flags,
            )
            for r in results
        ],
        sell_count=sum(1 for r in results if r.action == "SELL"),
        watch_count=sum(1 for r in results if r.action == "WATCH"),
        hold_count=sum(1 for r in results if r.action == "HOLD"),
        leveraged_count=sum(1 for r in results if r.action == "LEVERAGED_ETF"),
        run_at=datetime.now(timezone.utc).isoformat(),
    )
