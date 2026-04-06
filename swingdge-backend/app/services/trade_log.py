"""
Trade execution logger.

Writes a TradeHistory record when a TradePlan reaches a terminal state:
  stopped   — stop loss hit (loss)
  hit_t2    — target 2 hit (win)
  expired   — plan expired without entry (neutral — not logged)
  cancelled — user cancelled (neutral — not logged)

Only "stopped" and "hit_t2" represent real executed trades.
For "hit_t1" we do NOT log yet — trade is still open.

Called from:
  - PATCH /api/trades/plans/:id/status  (manual close)
  - trigger/price-check                 (automated close)
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.trade_plan import TradePlan
from app.models.trade_history import TradeHistory
from app.models.account import Account


# Terminal statuses that represent a completed trade
CLOSED_STATUSES = {"stopped", "hit_t2"}


async def log_trade_close(db: AsyncSession, plan: TradePlan) -> TradeHistory | None:
    """
    Write a TradeHistory row for a completed trade.
    Skips non-terminal statuses (pending, active, hit_t1, expired, cancelled).
    Returns the new TradeHistory row, or None if skipped.
    """
    if plan.status not in CLOSED_STATUSES:
        return None

    # Determine exit price
    exit_price = float(plan.closed_price) if plan.closed_price is not None else None
    if exit_price is None:
        # Fallback: use stop_loss for stopped, target_2 for hit_t2
        exit_price = float(plan.stop_loss) if plan.status == "stopped" else float(plan.target_2)

    entry_price = (float(plan.entry_low) + float(plan.entry_high)) / 2
    shares = float(plan.position_size_shares)

    # Gross P&L in trade currency
    gross_pnl = (exit_price - entry_price) * shares
    fx_cost = float(plan.fx_cost_pct or 0) / 100 * float(plan.position_size_dollars or 0)
    net_pnl = float(plan.actual_pnl) if plan.actual_pnl is not None else (gross_pnl - fx_cost)

    result = "win" if net_pnl > 0 else ("loss" if net_pnl < 0 else "breakeven")

    # Hold days
    entered_at = plan.created_at or datetime.now(timezone.utc)
    exited_at = plan.closed_at or datetime.now(timezone.utc)
    # Make timezone-aware if naive
    if entered_at.tzinfo is None:
        entered_at = entered_at.replace(tzinfo=timezone.utc)
    if exited_at.tzinfo is None:
        exited_at = exited_at.replace(tzinfo=timezone.utc)
    hold_days = max(0, (exited_at - entered_at).days)

    # Get any account_id from the accounts table (single-user — take first)
    acc_res = await db.execute(select(Account.id).limit(1))
    account_id = acc_res.scalar_one_or_none() or 1

    history = TradeHistory(
        trade_plan_id=plan.id,
        account_id=account_id,
        ticker=plan.ticker,
        exchange=plan.exchange,
        currency=plan.currency,
        entry_price=entry_price,
        exit_price=exit_price,
        shares=shares,
        gross_pnl=round(gross_pnl, 2),
        fx_cost=round(fx_cost, 2),
        net_pnl=round(net_pnl, 2),
        hold_days=hold_days,
        result=result,
        signal_type=plan.signal_type,
        entered_at=entered_at,
        exited_at=exited_at,
    )
    db.add(history)
    # Caller is responsible for commit
    return history
