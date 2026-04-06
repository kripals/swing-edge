"""
Trigger endpoints — called by GitHub Actions cron workflows.
All require Authorization: Bearer <TRIGGER_SECRET> header.

Scheduled jobs:
  morning-scan    → 9:45 AM ET  — full scanner pipeline + Telegram briefing
  price-check     → every 15min — check active trades vs entry/stop/target
  daily-summary   → 4:45 PM ET  — Telegram EOD digest
  macro-update    → 6:00 PM ET  — warm BoC + commodities cache
  earnings-check  → 8:00 AM ET  — warn about holdings with earnings this week
  portfolio-sync  → 2x daily    — SnapTrade sync
  sector-update   → 4:30 PM ET  — warm sector ETF cache
  cache-cleanup   → daily       — purge expired cache rows
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select, desc, func
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


# ── morning-scan ──────────────────────────────────────────────────────────────

@router.post("/morning-scan")
async def trigger_morning_scan(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import scanner as scanner_svc
        from app.services import telegram as tg
        from app.models.scan_result import ScanResult

        today = date.today()

        # Run full scan
        candidates = await scanner_svc.run_scan(db)

        # Persist results (delete today's existing rows first to avoid dupes)
        await db.execute(
            ScanResult.__table__.delete().where(ScanResult.scan_date == today)
        )
        for c in candidates:
            row = ScanResult(
                scan_date=today,
                ticker=c.ticker,
                exchange=c.exchange,
                current_price=c.current_price,
                signal_type=c.signal_type,
                signal_strength=c.signal_strength,
                rsi_14=c.rsi_14,
                macd_histogram=c.macd_histogram,
                volume_ratio=c.volume_ratio,
                above_sma_50=c.above_sma_50,
                atr_14=c.atr_14,
                relative_strength=c.relative_strength,
                sector=c.sector,
                notes=c.notes,
            )
            db.add(row)
        await db.commit()

        # Count tickers scanned (approximate — from model ticker universe)
        from app.models.ticker import Ticker
        ticker_count_res = await db.execute(
            select(func.count()).select_from(Ticker).where(Ticker.is_active == True)
        )
        total_scanned = ticker_count_res.scalar_one_or_none() or 0

        # Send Telegram morning briefing
        candidate_dicts = [
            {
                "ticker": c.ticker,
                "signal_type": c.signal_type,
                "signal_strength": c.signal_strength,
                "current_price": c.current_price,
            }
            for c in candidates
        ]
        message = tg.fmt_morning_briefing(
            candidates=candidate_dicts,
            scan_date=today.isoformat(),
            total_scanned=total_scanned,
        )
        await tg.send_alert(
            db,
            alert_type="morning_briefing",
            message=message,
            priority="high",
        )

        return f"Scanned {total_scanned} tickers, found {len(candidates)} candidates"

    return await _run_timed("morning-scan", _job())


# ── price-check ───────────────────────────────────────────────────────────────

@router.post("/price-check")
async def trigger_price_check(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import twelve_data
        from app.services import telegram as tg
        from app.services import trade_log as trade_log_svc
        from app.models.trade_plan import TradePlan

        # Fetch all active/watching plans
        result = await db.execute(
            select(TradePlan).where(TradePlan.status.in_(["pending", "active", "hit_t1"]))
        )
        plans = result.scalars().all()

        if not plans:
            return "No active plans to check"

        tickers = list({p.ticker for p in plans})
        quotes = await twelve_data.get_batch_quotes(db, tickers)

        alerts_sent = 0
        updates = 0

        for plan in plans:
            q = quotes.get(plan.ticker)
            if not q or not q.get("close"):
                continue

            price = float(q["close"])
            stop = float(plan.stop_loss)
            t1 = float(plan.target_1)
            t2 = float(plan.target_2)
            entry_high = float(plan.entry_high)

            # ── Check stop hit ──
            if price <= stop and plan.status in ("active", "hit_t1"):
                plan.status = "stopped"
                plan.closed_price = price
                plan.closed_at = datetime.now(timezone.utc)
                await trade_log_svc.log_trade_close(db, plan)
                msg = tg.fmt_stop_hit(plan.ticker, price, stop)
                sent = await tg.send_alert(db, "stop_hit", msg, ticker=plan.ticker, priority="critical")
                if sent:
                    alerts_sent += 1
                updates += 1
                continue

            # ── Check T2 hit ──
            if price >= t2 and plan.status == "hit_t1":
                plan.status = "hit_t2"
                plan.closed_price = price
                plan.closed_at = datetime.now(timezone.utc)
                await trade_log_svc.log_trade_close(db, plan)
                msg = tg.fmt_target_hit(plan.ticker, 2, price)
                sent = await tg.send_alert(db, "target_2_hit", msg, ticker=plan.ticker, priority="high")
                if sent:
                    alerts_sent += 1
                updates += 1
                continue

            # ── Check T1 hit ──
            if price >= t1 and plan.status == "active":
                plan.status = "hit_t1"
                msg = tg.fmt_target_hit(plan.ticker, 1, price)
                sent = await tg.send_alert(db, "target_1_hit", msg, ticker=plan.ticker, priority="high")
                if sent:
                    alerts_sent += 1
                updates += 1
                continue

            # ── Check stop approaching (within 2%) — only for active plans ──
            if plan.status == "active":
                pct_from_stop = (price - stop) / stop * 100
                if 0 < pct_from_stop < 2.0:
                    msg = tg.fmt_stop_approaching(plan.ticker, price, stop, pct_from_stop)
                    sent = await tg.send_alert(db, "stop_approaching", msg, ticker=plan.ticker, priority="medium")
                    if sent:
                        alerts_sent += 1

            # ── Check entry signal — price entered entry zone ──
            if plan.status == "pending":
                entry_low = float(plan.entry_low)
                if entry_low <= price <= entry_high:
                    msg = tg.fmt_entry_signal(
                        ticker=plan.ticker,
                        signal_type=plan.signal_type or "SETUP",
                        entry_low=entry_low,
                        entry_high=entry_high,
                        stop_loss=stop,
                        target_1=t1,
                        target_2=t2,
                        rr=float(plan.risk_reward_ratio),
                        signal_strength=float(plan.signal_score or 0),
                        fx_cost=float(plan.fx_cost_pct or 0),
                    )
                    sent = await tg.send_alert(db, "entry_signal", msg, ticker=plan.ticker, priority="high")
                    if sent:
                        alerts_sent += 1

        await db.commit()
        return f"Checked {len(plans)} plans — {updates} status updates, {alerts_sent} alerts sent"

    return await _run_timed("price-check", _job())


# ── daily-summary ─────────────────────────────────────────────────────────────

@router.post("/daily-summary")
async def trigger_daily_summary(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import portfolio as portfolio_svc
        from app.services import telegram as tg
        from app.models.trade_plan import TradePlan
        from app.models.scan_result import ScanResult
        from app.models.alert import Alert

        today = date.today()

        # Portfolio value
        try:
            summary = await portfolio_svc.get_portfolio_summary(db)
            total_value = summary.total_value_cad
            daily_change = summary.total_unrealized_pnl  # best proxy we have
            daily_change_pct = (daily_change / (total_value - daily_change) * 100) if total_value else 0.0
        except Exception:
            total_value = 0.0
            daily_change = 0.0
            daily_change_pct = 0.0

        # Active trades count
        active_res = await db.execute(
            select(func.count()).select_from(TradePlan)
            .where(TradePlan.status.in_(["pending", "active", "hit_t1"]))
        )
        active_trades = active_res.scalar_one_or_none() or 0

        # Scan candidates today
        scan_res = await db.execute(
            select(func.count()).select_from(ScanResult)
            .where(ScanResult.scan_date == today)
        )
        candidates_today = scan_res.scalar_one_or_none() or 0

        # Alerts sent today
        alerts_res = await db.execute(
            select(func.count()).select_from(Alert)
            .where(func.date(Alert.sent_at) == today)
        )
        alerts_today = alerts_res.scalar_one_or_none() or 0

        message = tg.fmt_daily_summary(
            portfolio_value=total_value,
            daily_change=daily_change,
            daily_change_pct=daily_change_pct,
            active_trades=active_trades,
            candidates_today=candidates_today,
            alerts_today=alerts_today,
        )
        await tg.send_alert(db, "daily_summary", message, priority="medium")
        return "Daily summary sent"

    return await _run_timed("daily-summary", _job())


# ── macro-update ──────────────────────────────────────────────────────────────

@router.post("/macro-update")
async def trigger_macro_update(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import market as market_svc
        from app.services import telegram as tg

        macro = await market_svc.get_macro(db)

        # Format a quick summary and send
        overnight = f"{macro.overnight_rate['value']}%" if macro.overnight_rate else "—"
        usd_cad = f"{macro.usd_cad['value']:.4f}" if macro.usd_cad else "—"
        wti = f"${macro.wti_oil:.2f}" if macro.wti_oil else "—"
        gold = f"${macro.gold:.2f}" if macro.gold else "—"

        message = tg.fmt_macro_update(overnight, usd_cad, wti, gold)
        await tg.send_alert(db, "scan_complete", message, priority="low")
        return f"Macro updated: BoC={overnight}, USD/CAD={usd_cad}, WTI={wti}, Gold={gold}"

    return await _run_timed("macro-update", _job())


# ── earnings-check ────────────────────────────────────────────────────────────

@router.post("/earnings-check")
async def trigger_earnings_check(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import earnings as earn_svc
        from app.services import telegram as tg
        from app.models.holding import Holding
        from app.models.trade_plan import TradePlan

        # Collect unique tickers from holdings + active plans
        holdings_res = await db.execute(select(Holding.ticker).distinct())
        holding_tickers = {row[0] for row in holdings_res.fetchall()}

        plans_res = await db.execute(
            select(TradePlan.ticker).where(
                TradePlan.status.in_(["pending", "active", "hit_t1"])
            ).distinct()
        )
        plan_tickers = {row[0] for row in plans_res.fetchall()}

        all_tickers = holding_tickers | plan_tickers
        warnings_sent = 0

        for ticker in all_tickers:
            try:
                info = await earn_svc.get_next_earnings(db, ticker)
                if info and info.get("earnings_days_away") is not None:
                    days_away = info["earnings_days_away"]
                    if days_away <= 7:  # warn up to 7 days ahead
                        in_blackout = days_away <= 5
                        msg = tg.fmt_earnings_warning(
                            ticker=ticker,
                            days_away=days_away,
                            earnings_date=str(info.get("next_earnings_date", "")),
                            in_blackout=in_blackout,
                        )
                        priority = "critical" if in_blackout else "medium"
                        sent = await tg.send_alert(
                            db, "earnings_warning", msg,
                            ticker=ticker, priority=priority,
                        )
                        if sent:
                            warnings_sent += 1
            except Exception:
                continue

        return f"Checked {len(all_tickers)} tickers — {warnings_sent} earnings warnings sent"

    return await _run_timed("earnings-check", _job())


# ── portfolio-sync ────────────────────────────────────────────────────────────

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


# ── sector-update ─────────────────────────────────────────────────────────────

@router.post("/sector-update")
async def trigger_sector_update(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import market as market_svc

        sectors = await market_svc.get_sectors(db)
        if not sectors:
            return "No sector data returned"

        best = max(sectors, key=lambda s: s.change_pct or 0.0)
        worst = min(sectors, key=lambda s: s.change_pct or 0.0)
        return (
            f"Updated {len(sectors)} sectors. "
            f"Best: {best.sector} {best.ticker} {best.change_pct:+.2f}%  "
            f"Worst: {worst.sector} {worst.ticker} {worst.change_pct:+.2f}%"
        )

    return await _run_timed("sector-update", _job())


# ── cache-cleanup ─────────────────────────────────────────────────────────────

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
