"""
Trigger endpoints — called by GitHub Actions cron workflows.
All require Authorization: Bearer <TRIGGER_SECRET> header.

Scheduled jobs:
  morning-scan        → 9:45 AM ET  — full scanner pipeline + Telegram briefing
  price-check         → every 15min — check active trades vs entry/stop/target
  daily-summary       → 4:45 PM ET  — Telegram EOD digest
  macro-update        → 6:00 PM ET  — warm BoC + commodities cache
  earnings-check      → 8:00 AM ET  — warn about holdings with earnings this week
  portfolio-sync      → 2x daily    — SnapTrade sync
  sector-update       → 4:30 PM ET  — warm sector ETF cache
  cache-cleanup       → daily       — purge expired cache rows + deactivate expired tickers
  portfolio-snapshot  → 4:15 PM ET  — write daily portfolio value to market_snapshots
  ticker-discovery    → weekly Sun  — sync TSX screener, permanently add new tickers
  momentum-watchlist  → daily       — add today's TSX gainers for 7-day temporary scan
  portfolio-advisor   → 4:00 PM ET  — HOLD/WATCH/SELL recommendations for existing holdings
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.utils.auth import verify_trigger_secret
from app.services import cache as cache_svc
from app.models.ticker import Ticker

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
        logger.exception("Job %s failed", job_name)
        return TriggerResult(
            job=job_name,
            status="error",
            message=str(exc),
            triggered_at=start.isoformat(),
            duration_ms=duration,
        )


# ── morning-scan ──────────────────────────────────────────────────────────────

async def _morning_scan_bg() -> None:
    """
    Background task: runs the full scan with its own DB session.
    Called by the trigger endpoint so the HTTP response returns immediately,
    allowing GitHub Actions (10-min timeout) to succeed even when the scan
    takes 30-60+ minutes due to Twelve Data rate limiting.
    """
    from app.services import scanner as scanner_svc
    from app.services import telegram as tg
    from app.models.scan_result import ScanResult
    from app.models.ticker import Ticker

    logger.info("morning-scan background task started")
    start = datetime.now(timezone.utc)

    try:
        async with AsyncSessionLocal() as db:
            today = date.today()

            candidates = await scanner_svc.run_scan(db)

            new_rows = [
                ScanResult(
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
                    high_52w=c.high_52w,
                    adx_14=c.adx_14,
                    sector=c.sector,
                    notes=c.notes,
                )
                for c in candidates
            ]
            # Atomic: delete old + insert new in one transaction so a crash
            # mid-write never leaves the table empty.
            async with db.begin():
                await db.execute(
                    ScanResult.__table__.delete().where(ScanResult.scan_date == today)
                )
                db.add_all(new_rows)

            ticker_count_res = await db.execute(
                select(func.count()).select_from(Ticker).where(Ticker.is_active == True)
            )
            total_scanned = ticker_count_res.scalar_one_or_none() or 0

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
            await tg.send_alert(db, alert_type="morning_briefing", message=message, priority="high")

            duration_s = int((datetime.now(timezone.utc) - start).total_seconds())
            logger.info("morning-scan done: %d tickers, %d candidates, %ds", total_scanned, len(candidates), duration_s)

    except Exception:
        logger.exception("morning-scan background task failed")


@router.post("/morning-scan")
async def trigger_morning_scan(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Accepts the scan request and returns immediately.
    The actual scan runs as a background task (can take 30-60+ min on cold cache).
    """
    verify_trigger_secret(authorization)
    background_tasks.add_task(_morning_scan_bg)
    return {
        "job": "morning-scan",
        "status": "started",
        "message": "Scan running in background — check Telegram for results",
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }


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
        from app.utils.market_calendar import is_market_open

        if not is_market_open():
            return "Market closed today (holiday or weekend) — skipping price-check"

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
            if not q or not q.get("price"):
                continue

            price = float(q["price"])
            stop = float(plan.stop_loss)
            t1 = float(plan.target_1)
            t2 = float(plan.target_2)
            entry_high = float(plan.entry_high)

            # ── P&L helper (entry_mid × shares) ──
            entry_mid = (float(plan.entry_low) + float(plan.entry_high)) / 2
            shares = float(plan.position_size_shares or 0)
            pnl = round((price - entry_mid) * shares, 2) if shares > 0 else None

            # ── Check stop hit ──
            if price <= stop and plan.status in ("active", "hit_t1"):
                plan.status = "stopped"
                plan.closed_price = price
                plan.closed_at = datetime.now(timezone.utc)
                await trade_log_svc.log_trade_close(db, plan)
                msg = tg.fmt_stop_hit(plan.ticker, price, stop, pnl=pnl)
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
                msg = tg.fmt_target_hit(plan.ticker, 2, price, pnl=pnl)
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
        from app.models.market_snapshot import MarketSnapshot
        from datetime import timedelta

        today = date.today()
        yesterday = today - timedelta(days=1)

        # Portfolio value
        try:
            summary = await portfolio_svc.get_portfolio_summary(db)
            total_value = summary.total_value_cad

            # Try to get yesterday's snapshot for true daily change
            yesterday_snap = await db.execute(
                select(MarketSnapshot).where(MarketSnapshot.date == yesterday)
            )
            yesterday_row = yesterday_snap.scalar_one_or_none()

            if yesterday_row and yesterday_row.portfolio_value_cad:
                # True daily change vs yesterday's close
                total_pnl = total_value - float(yesterday_row.portfolio_value_cad)
                total_pnl_pct = (total_pnl / float(yesterday_row.portfolio_value_cad) * 100) if yesterday_row.portfolio_value_cad else 0.0
            else:
                # Fallback: report total unrealized P&L (since purchase)
                total_pnl = summary.total_unrealized_pnl
                total_pnl_pct = (total_pnl / (total_value - total_pnl) * 100) if (total_value - total_pnl) else 0.0
        except Exception:
            total_value = 0.0
            total_pnl = 0.0
            total_pnl_pct = 0.0

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
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
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
        wti = f"${macro.wti_oil['value']:.2f}" if macro.wti_oil else "—"
        gold = f"${macro.gold['value']:.2f}" if macro.gold else "—"

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
                in_blackout, earnings_date, days_away = await earn_svc.is_in_blackout(db, ticker)
                if earnings_date is not None and days_away is not None and days_away <= 7:
                    msg = tg.fmt_earnings_warning(
                        ticker=ticker,
                        days_away=days_away,
                        earnings_date=str(earnings_date),
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


# ── portfolio-snapshot ────────────────────────────────────────────────────────

@router.post("/portfolio-snapshot")
async def trigger_portfolio_snapshot(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    """
    Write today's total portfolio value to market_snapshots table.
    Run at 4:15 PM ET (after market close, before daily-summary at 4:45 PM).
    Enables true daily P&L diff in daily-summary (today vs yesterday snapshot).
    """
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import portfolio as portfolio_svc
        from app.services import market as market_svc
        from app.models.market_snapshot import MarketSnapshot

        today = date.today()

        # Get portfolio value
        summary = await portfolio_svc.get_portfolio_summary(db)
        total_value = summary.total_value_cad

        # Get macro snapshot values to store alongside (reuse cached data — no new API calls)
        try:
            macro = await market_svc.get_macro(db)
            usd_cad = float(macro.usd_cad["value"]) if macro.usd_cad else None
            boc_rate = float(macro.overnight_rate["value"]) if macro.overnight_rate else None
            wti = float(macro.wti_oil["value"]) if macro.wti_oil else None
            gold = float(macro.gold["value"]) if macro.gold else None
            nat_gas = float(macro.natural_gas["value"]) if macro.natural_gas else None
            copper = float(macro.copper["value"]) if macro.copper else None
            cpi = float(macro.cpi["value"]) if macro.cpi else None
        except Exception:
            usd_cad = boc_rate = wti = gold = nat_gas = copper = cpi = None

        # Upsert: update if today's row already exists, insert otherwise
        existing = await db.execute(
            select(MarketSnapshot).where(MarketSnapshot.date == today)
        )
        snapshot = existing.scalar_one_or_none()

        if snapshot is None:
            snapshot = MarketSnapshot(date=today)
            db.add(snapshot)

        snapshot.usd_cad = usd_cad
        snapshot.boc_rate = boc_rate
        snapshot.wti_oil = wti
        snapshot.gold = gold
        snapshot.nat_gas = nat_gas
        snapshot.copper = copper
        snapshot.cpi = cpi
        snapshot.portfolio_value_cad = total_value

        await db.commit()

        return f"Snapshot saved for {today}: portfolio ${total_value:,.2f} CAD"

    return await _run_timed("portfolio-snapshot", _job())


# ── cache-cleanup ─────────────────────────────────────────────────────────────

@router.post("/cache-cleanup")
async def trigger_cache_cleanup(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    verify_trigger_secret(authorization)

    async def _job():
        # 1. Purge expired API cache rows
        deleted = await cache_svc.cache_cleanup(db)

        # 2. Deactivate dynamic tickers whose 7-day window has expired
        now = datetime.now(timezone.utc)
        expired_res = await db.execute(
            select(Ticker).where(
                Ticker.expires_at.isnot(None),
                Ticker.expires_at < now,
                Ticker.is_active == True,
            )
        )
        expired_tickers = expired_res.scalars().all()
        for t in expired_tickers:
            t.is_active = False
        if expired_tickers:
            await db.commit()

        return (
            f"Removed {deleted} expired cache entries; "
            f"deactivated {len(expired_tickers)} expired dynamic tickers"
        )

    return await _run_timed("cache-cleanup", _job())


# ── ticker-discovery ──────────────────────────────────────────────────────────

@router.post("/ticker-discovery")
async def trigger_ticker_discovery(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    """
    Weekly job (Sunday 6 AM ET): sync TSX screener results into ticker_universe.
    - Upserts new tickers that meet market cap + volume thresholds (permanent additions).
    - Deactivates tickers no longer returned by screener and not manually added.
    """
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import fmp as fmp_svc
        from app.services import telegram as tg

        screener_results = await fmp_svc.get_tsx_screener(db)
        if not screener_results:
            return "Screener returned no results — skipping"

        screener_tickers = {r["ticker"] for r in screener_results}

        # Load all existing ticker_universe rows
        existing_res = await db.execute(select(Ticker))
        existing = {t.ticker: t for t in existing_res.scalars().all()}

        added = 0
        deactivated = 0

        for item in screener_results:
            ticker_sym = item["ticker"]
            if ticker_sym in existing:
                # Re-activate if it was previously deactivated by screener
                row = existing[ticker_sym]
                if not row.is_active and row.discovery_source == "fmp_screener":
                    row.is_active = True
            else:
                # New ticker — add permanently (no expires_at)
                new_row = Ticker(
                    ticker=ticker_sym,
                    exchange="TSX",
                    name=item.get("name"),
                    sector=item.get("sector"),
                    currency="CAD",
                    is_etf=False,
                    is_active=True,
                    twelve_data_symbol=ticker_sym.replace(".TO", ":TSX") if ticker_sym.endswith(".TO") else ticker_sym,
                    discovery_source="fmp_screener",
                )
                db.add(new_row)
                added += 1

        # Deactivate screener-sourced tickers no longer in results (delisted guard)
        for ticker_sym, row in existing.items():
            if (
                row.discovery_source == "fmp_screener"
                and row.is_active
                and ticker_sym not in screener_tickers
            ):
                row.is_active = False
                deactivated += 1

        await db.commit()

        summary = f"Ticker discovery: +{added} added, -{deactivated} deactivated ({len(screener_tickers)} in screener)"
        await tg.send_message(f"📊 <b>Ticker Discovery</b>\n{summary}")
        return summary

    return await _run_timed("ticker-discovery", _job())


# ── momentum-watchlist ────────────────────────────────────────────────────────

@router.post("/momentum-watchlist")
async def trigger_momentum_watchlist(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    """
    Daily job (10:30 AM ET): add today's top TSX gainers as temporary scan candidates.
    Tickers expire after 7 days and are deactivated by cache-cleanup.
    Only adds tickers NOT already in ticker_universe.
    """
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import fmp as fmp_svc
        from datetime import timedelta

        gainers = await fmp_svc.get_tsx_gainers(db)
        if not gainers:
            return "No TSX gainers returned today"

        # Load existing tickers to avoid duplicates
        existing_res = await db.execute(select(Ticker.ticker))
        existing_symbols = {row[0] for row in existing_res.fetchall()}

        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=7)

        added = 0
        for item in gainers:
            ticker_sym = item["ticker"]
            if ticker_sym in existing_symbols:
                continue
            new_row = Ticker(
                ticker=ticker_sym,
                exchange="TSX",
                name=item.get("name"),
                sector=None,
                currency="CAD",
                is_etf=False,
                is_active=True,
                twelve_data_symbol=ticker_sym.replace(".TO", ":TSX") if ticker_sym.endswith(".TO") else ticker_sym,
                discovery_source="momentum",
                expires_at=expires,
            )
            db.add(new_row)
            added += 1

        if added:
            await db.commit()

        return f"Momentum watchlist: added {added} temporary tickers (expire {expires.date()})"

    return await _run_timed("momentum-watchlist", _job())


# ── portfolio-advisor ─────────────────────────────────────────────────────────

@router.post("/portfolio-advisor")
async def trigger_portfolio_advisor(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TriggerResult:
    """
    Daily job (4:00 PM ET): analyze all holdings and send HOLD/WATCH/SELL recommendations via Telegram.
    Runs before daily-summary (4:45 PM ET) so advice is fresh when the summary arrives.
    """
    verify_trigger_secret(authorization)

    async def _job():
        from app.services import advisor as advisor_svc
        from app.services import telegram as tg

        results = await advisor_svc.analyze_holdings(db)
        if not results:
            return "No holdings to analyze"

        message = tg.fmt_portfolio_advice(results)
        await tg.send_alert(db, "portfolio_advice", message, priority="medium")

        sell_count = sum(1 for r in results if r.action == "SELL")
        watch_count = sum(1 for r in results if r.action == "WATCH")
        hold_count = sum(1 for r in results if r.action == "HOLD")
        return f"Portfolio advice sent: {sell_count} SELL, {watch_count} WATCH, {hold_count} HOLD"

    return await _run_timed("portfolio-advisor", _job())
