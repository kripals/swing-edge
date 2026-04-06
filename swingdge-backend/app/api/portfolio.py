from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import portfolio as portfolio_svc
from app.utils.auth import verify_token
from app.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


# ── Response Models ───────────────────────────────────────────────────────────

class HoldingOut(BaseModel):
    id: int
    account_id: int
    account_name: str
    ticker: str
    exchange: str
    shares: float
    avg_cost: float
    currency: str
    current_price: float | None
    market_value_cad: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    sector: str | None
    is_leveraged_etf: bool
    has_fx_cost: bool
    flags: list[str]


class AccountOut(BaseModel):
    id: int
    name: str
    account_type: str
    currency: str
    balance: float
    contribution_room: float | None
    total_market_value_cad: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    holdings: list[HoldingOut]


class PortfolioSummaryOut(BaseModel):
    total_value_cad: float
    total_cost_cad: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    daily_change_cad: float
    daily_change_pct: float
    flags: list[str]
    sector_weights: dict[str, float]
    accounts: list[AccountOut]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=PortfolioSummaryOut)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
) -> PortfolioSummaryOut:
    summary = await portfolio_svc.get_portfolio_summary(db)

    accounts_out = []
    for acc in summary.accounts:
        holdings_out = [
            HoldingOut(
                id=h.id,
                account_id=h.account_id,
                account_name=h.account_name,
                ticker=h.ticker,
                exchange=h.exchange,
                shares=h.shares,
                avg_cost=h.avg_cost,
                currency=h.currency,
                current_price=h.current_price,
                market_value_cad=h.market_value_cad,
                cost_basis=h.cost_basis,
                unrealized_pnl=h.unrealized_pnl,
                unrealized_pnl_pct=h.unrealized_pnl_pct,
                sector=h.sector,
                is_leveraged_etf=h.is_leveraged_etf,
                has_fx_cost=h.has_fx_cost,
                flags=h.flags,
            )
            for h in acc.holdings
        ]
        accounts_out.append(AccountOut(
            id=acc.id,
            name=acc.name,
            account_type=acc.account_type,
            currency=acc.currency,
            balance=acc.balance,
            contribution_room=acc.contribution_room,
            total_market_value_cad=acc.total_market_value_cad,
            total_unrealized_pnl=acc.total_unrealized_pnl,
            total_unrealized_pnl_pct=acc.total_unrealized_pnl_pct,
            holdings=holdings_out,
        ))

    return PortfolioSummaryOut(
        total_value_cad=summary.total_value_cad,
        total_cost_cad=summary.total_cost_cad,
        total_unrealized_pnl=summary.total_unrealized_pnl,
        total_unrealized_pnl_pct=summary.total_unrealized_pnl_pct,
        daily_change_cad=summary.daily_change_cad,
        daily_change_pct=summary.daily_change_pct,
        flags=summary.flags,
        sector_weights=summary.sector_weights,
        accounts=accounts_out,
    )


@router.get("/holdings")
async def get_holdings(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
) -> list[dict]:
    result = await db.execute(
        text("""
            SELECT h.id, h.account_id, a.name as account_name, h.ticker, h.exchange,
                   h.shares, h.avg_cost, h.currency, h.current_price,
                   h.unrealized_pnl, h.unrealized_pnl_pct, h.sector,
                   h.is_leveraged_etf, h.has_fx_cost, h.updated_at
            FROM holdings h
            JOIN accounts a ON a.id = h.account_id
            ORDER BY h.account_id, h.ticker
        """)
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


@router.get("/accounts")
async def get_accounts(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
) -> list[dict]:
    result = await db.execute(
        text("SELECT id, name, broker, account_type, currency, has_usd_account, balance, contribution_room, updated_at FROM accounts ORDER BY id")
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


class AddHoldingRequest(BaseModel):
    account_id: int
    ticker: str
    exchange: str
    shares: float
    avg_cost: float
    currency: str
    sector: str | None = None


@router.get("/health")
async def get_portfolio_health(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
) -> dict:
    """
    Portfolio health check:
    - Open exposure (total market value of active trade plans as % of portfolio)
    - Risk at stake (sum of risk_amount on pending/active plans)
    - Max drawdown (worst cumulative loss from trade_history)
    - Active trade count vs max allowed
    - Sector concentration warnings
    - Position size warnings
    """
    from app.models.trade_plan import TradePlan
    from app.models.trade_history import TradeHistory

    # Portfolio total value
    summary = await portfolio_svc.get_portfolio_summary(db)
    total_cad = summary.total_value_cad or 1.0  # avoid div/0

    # ── Active trades ─────────────────────────────────────────────────────────
    active_res = await db.execute(
        text("""
            SELECT COUNT(*) as count,
                   COALESCE(SUM(position_size_dollars), 0) as open_exposure,
                   COALESCE(SUM(risk_amount), 0) as risk_at_stake
            FROM trade_plans
            WHERE status IN ('pending', 'active', 'hit_t1')
        """)
    )
    row = active_res.fetchone()
    active_count = int(row.count)
    open_exposure_cad = float(row.open_exposure)
    risk_at_stake_cad = float(row.risk_at_stake)
    open_exposure_pct = round(open_exposure_cad / total_cad * 100, 1)
    risk_at_stake_pct = round(risk_at_stake_cad / total_cad * 100, 1)

    # ── Max drawdown from trade history ───────────────────────────────────────
    history_res = await db.execute(
        text("SELECT net_pnl FROM trade_history ORDER BY exited_at ASC")
    )
    pnl_rows = [float(r.net_pnl) for r in history_res.fetchall()]

    max_drawdown = 0.0
    peak = 0.0
    cumulative = 0.0
    equity_curve = []
    for pnl in pnl_rows:
        cumulative += pnl
        equity_curve.append(round(cumulative, 2))
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    # Win rate
    wins = sum(1 for p in pnl_rows if p > 0)
    total_trades = len(pnl_rows)
    win_rate = round(wins / total_trades * 100, 1) if total_trades else 0.0
    total_pnl = round(sum(pnl_rows), 2)

    # ── Warnings ──────────────────────────────────────────────────────────────
    warnings = []
    if active_count >= settings.max_active_trades:
        warnings.append(f"At max active trades ({active_count}/{settings.max_active_trades})")
    if open_exposure_pct > 50:
        warnings.append(f"High open exposure: {open_exposure_pct}% of portfolio in active plans")
    if risk_at_stake_pct > 5:
        warnings.append(f"High risk at stake: {risk_at_stake_pct}% of portfolio at risk")
    for sector, weight in summary.sector_weights.items():
        if weight > 30:
            warnings.append(f"Sector overweight: {sector} at {weight:.0f}%")
    for flag in summary.flags:
        if flag not in warnings:
            warnings.append(flag)

    return {
        "total_value_cad": round(total_cad, 2),
        "active_trade_count": active_count,
        "max_active_trades": settings.max_active_trades,
        "open_exposure_cad": round(open_exposure_cad, 2),
        "open_exposure_pct": open_exposure_pct,
        "risk_at_stake_cad": round(risk_at_stake_cad, 2),
        "risk_at_stake_pct": risk_at_stake_pct,
        "max_drawdown_cad": round(max_drawdown, 2),
        "total_closed_trades": total_trades,
        "win_rate_pct": win_rate,
        "total_realized_pnl": total_pnl,
        "equity_curve": equity_curve,
        "sector_weights": summary.sector_weights,
        "warnings": warnings,
    }


@router.post("/holdings", status_code=201)
async def add_holding(
    body: AddHoldingRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
) -> dict:
    has_fx = body.currency == "USD"
    result = await db.execute(
        text("""
            INSERT INTO holdings (account_id, ticker, exchange, shares, avg_cost, currency, sector, has_fx_cost)
            VALUES (:account_id, :ticker, :exchange, :shares, :avg_cost, :currency, :sector, :has_fx)
            ON CONFLICT DO NOTHING
            RETURNING id
        """),
        {**body.model_dump(), "has_fx": has_fx},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=409, detail="Holding already exists")
    await db.commit()
    return {"id": row[0], "ticker": body.ticker}
