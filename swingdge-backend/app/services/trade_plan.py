"""
Trade plan generator.

Given a scan candidate (or a manually selected ticker), generates a full
trade plan:

  entry_low / entry_high — buy zone (current price ± small buffer)
  stop_loss              — below entry, based on ATR or BB lower
  target_1               — 1.5× risk from entry (partial profit)
  target_2               — 3× risk from entry (full target, meets 2:1 R/R)
  position_size_dollars  — 1% of account at risk
  position_size_shares   — dollars / entry midpoint
  risk_reward_ratio      — (target_2 - entry_mid) / (entry_mid - stop_loss)
  fx_cost_pct            — 0% for CAD, 3% round-trip for USD (no USD account)
  net_gain_after_fx      — (target_2 - entry_mid) / entry_mid * 100 - fx_cost_pct

Stop logic (in priority order):
  1. ATR stop: entry_mid - 1.5 × ATR14  (preferred — volatility-adjusted)
  2. BB lower: bb_lower - 0.5%           (fallback if ATR unavailable)
  3. 5% flat stop                        (last resort)

Entry zone: ±0.5% around current price (tight zone for limit orders).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade_plan import TradePlan
from app.models.ticker import Ticker
from app.services import rules as rules_svc
from app.services import twelve_data
from app.services import earnings as earn_svc
from app.services import indicators as ind_svc


@dataclass
class TradePlanResult:
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
    pivot_levels: dict | None   # {pivot, s1, s2, r1, r2} from previous day OHLC
    violations: list[str]       # empty = valid trade


# ── Main generator ────────────────────────────────────────────────────────────

async def generate(
    db: AsyncSession,
    ticker: str,
    signal_type: str | None = None,
    signal_score: float | None = None,
    account_value_cad: float = 7000.0,  # fallback — ideally pass real account total
) -> TradePlanResult:
    """
    Generate a trade plan for a ticker. Call after scanner surfaces a candidate,
    or directly from the trade plan endpoint.
    """
    # ── Fetch data ────────────────────────────────────────────────────────────
    quotes = await twelve_data.get_batch_quotes(db, [ticker])
    quote = quotes.get(ticker, {})
    price = quote.get("price")
    if price is None:
        raise ValueError(f"No quote available for {ticker}")

    ind = await twelve_data.get_indicators(db, ticker)
    try:
        candles = await twelve_data.get_daily_ohlcv(db, ticker, output_size=30)
    except Exception:
        candles = []
    extras = ind_svc.compute_extras(candles)
    ind.update(extras)

    # ── Ticker metadata ───────────────────────────────────────────────────────
    ticker_row = await _get_ticker(db, ticker)
    currency = ticker_row.currency if ticker_row else ("USD" if _is_us(ticker) else "CAD")
    exchange = ticker_row.exchange if ticker_row else ("NYSE" if _is_us(ticker) else "TSX")
    sector = ticker_row.sector if ticker_row else None

    # ── Pivot points (classic formula from previous day OHLC) ────────────────
    pivots = ind_svc.compute_pivot_points(candles)

    # ── Entry zone ────────────────────────────────────────────────────────────
    entry_low = round(price * 0.995, 4)
    entry_high = round(price * 1.005, 4)

    # Snap entry_low to nearest support pivot (S1 or S2) if within 1% of price
    if pivots:
        for support in (pivots["s1"], pivots["s2"]):
            if support > 0 and abs(support - price) / price <= 0.01:
                entry_low = round(min(entry_low, support), 4)
                break

    entry_mid = round((entry_low + entry_high) / 2, 4)

    # ── Stop loss ─────────────────────────────────────────────────────────────
    atr = ind.get("atr_14")
    bb_lower = ind.get("bb_lower")
    stop_loss = _calc_stop(entry_mid, atr, bb_lower)

    # ── Risk per share ────────────────────────────────────────────────────────
    risk_per_share = entry_mid - stop_loss
    if risk_per_share <= 0:
        risk_per_share = entry_mid * 0.05  # fallback 5%

    # ── Targets (T1 = 1.5R, T2 = 3R → meets 2:1 R/R at midpoint of T1+T2) ──
    target_1 = round(entry_mid + 1.5 * risk_per_share, 4)
    target_2 = round(entry_mid + 3.0 * risk_per_share, 4)

    # ── R/R ratio (using T2 as the full target) ───────────────────────────────
    rr = round((target_2 - entry_mid) / risk_per_share, 2)

    # ── Position sizing — 1% of account at risk ───────────────────────────────
    risk_pct = await rules_svc.risk_pct(db)
    risk_dollars = round(account_value_cad * risk_pct / 100, 2)
    shares = round(risk_dollars / risk_per_share, 4) if risk_per_share > 0 else 0
    position_dollars = round(shares * entry_mid, 2)

    # ── FX cost ───────────────────────────────────────────────────────────────
    is_us = currency == "USD"
    usd_account = await rules_svc.has_usd_account(db)
    fee_one_way = await rules_svc.fx_fee_pct(db)
    fx_cost = 0.0 if (not is_us or usd_account) else fee_one_way * 2  # round-trip

    # ── Net gain after FX ─────────────────────────────────────────────────────
    gross_gain_pct = (target_2 - entry_mid) / entry_mid * 100
    net_gain = round(gross_gain_pct - fx_cost, 2) if fx_cost > 0 else None

    fx_warning_threshold = await rules_svc.fx_warning_threshold(db)
    fx_warning = is_us and not usd_account and (net_gain is not None and net_gain < fx_warning_threshold)

    # ── Earnings ──────────────────────────────────────────────────────────────
    _, earnings_date, days_away = await earn_svc.is_in_blackout(db, ticker)

    # ── Rule violations ───────────────────────────────────────────────────────
    violations = await _check_violations(db, ticker, rr, fx_cost, net_gain, days_away, account_value_cad, position_dollars)

    return TradePlanResult(
        ticker=ticker,
        exchange=exchange,
        currency=currency,
        sector=sector,
        current_price=price,
        entry_low=entry_low,
        entry_high=entry_high,
        entry_mid=entry_mid,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        risk_reward_ratio=rr,
        position_size_dollars=position_dollars,
        position_size_shares=shares,
        risk_amount=risk_dollars,
        fx_cost_pct=fx_cost,
        net_gain_after_fx=net_gain,
        fx_warning=fx_warning,
        earnings_date=earnings_date,
        earnings_days_away=days_away,
        signal_type=signal_type,
        signal_score=signal_score,
        pivot_levels=pivots,
        violations=violations,
    )


async def save_plan(db: AsyncSession, plan: TradePlanResult) -> TradePlan:
    """Persist a TradePlanResult to the trade_plans table."""
    expiry_days = await rules_svc.trade_expiry_days(db)
    row = TradePlan(
        ticker=plan.ticker,
        exchange=plan.exchange,
        currency=plan.currency,
        sector=plan.sector,
        current_price=plan.current_price,
        entry_low=plan.entry_low,
        entry_high=plan.entry_high,
        stop_loss=plan.stop_loss,
        target_1=plan.target_1,
        target_2=plan.target_2,
        risk_reward_ratio=plan.risk_reward_ratio,
        position_size_dollars=plan.position_size_dollars,
        position_size_shares=plan.position_size_shares,
        risk_amount=plan.risk_amount,
        fx_cost_pct=plan.fx_cost_pct,
        net_gain_after_fx=plan.net_gain_after_fx,
        earnings_date=plan.earnings_date,
        earnings_days_away=plan.earnings_days_away,
        signal_type=plan.signal_type,
        signal_score=plan.signal_score,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=expiry_days),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ── Helpers ───────────────────────────────────────────────────────────────────

def _calc_stop(entry_mid: float, atr: float | None, bb_lower: float | None) -> float:
    if atr is not None:
        return round(entry_mid - 1.5 * atr, 4)
    if bb_lower is not None:
        return round(bb_lower * 0.995, 4)
    return round(entry_mid * 0.95, 4)   # 5% flat stop


def _is_us(ticker: str) -> bool:
    return not ticker.endswith(".TO")


async def _get_ticker(db: AsyncSession, ticker: str) -> Ticker | None:
    result = await db.execute(select(Ticker).where(Ticker.ticker == ticker))
    return result.scalar_one_or_none()


async def _check_violations(
    db: AsyncSession,
    ticker: str,
    rr: float,
    fx_cost: float,
    net_gain: float | None,
    days_away: int | None,
    account_value: float,
    position_dollars: float,
) -> list[str]:
    violations: list[str] = []

    min_rr = await rules_svc.min_rr(db)
    if rr < min_rr:
        violations.append(f"R/R ratio {rr:.1f} below minimum {min_rr:.1f}")

    blackout = await rules_svc.earnings_blackout_days(db)
    if days_away is not None and 0 <= days_away <= blackout:
        violations.append(f"Earnings in {days_away} days (blackout is {blackout})")

    max_pos_pct = await rules_svc.max_position_pct(db)
    pos_pct = position_dollars / account_value * 100 if account_value > 0 else 0
    if pos_pct > max_pos_pct:
        violations.append(f"Position size {pos_pct:.1f}% exceeds max {max_pos_pct:.0f}%")

    if fx_cost > 0 and net_gain is not None:
        threshold = await rules_svc.fx_warning_threshold(db)
        if net_gain < threshold:
            violations.append(f"Net gain after FX only {net_gain:.1f}% (threshold: {threshold:.1f}%)")

    return violations
