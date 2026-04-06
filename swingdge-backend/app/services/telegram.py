"""
Telegram notification service.

Uses the Telegram Bot API directly via httpx (no library overhead).
Sends formatted messages to TELEGRAM_CHAT_ID using the bot token.

Alert types (from alert model):
  entry_signal      — new scanner candidate with trade setup
  stop_approaching  — price within 2% of stop loss
  stop_hit          — stop loss triggered
  target_1_hit      — T1 reached
  target_2_hit      — T2 reached
  earnings_warning  — holding/plan has earnings within 5 days
  daily_summary     — end-of-day digest
  morning_briefing  — pre-market scan summary
  scan_complete     — scanner finished (used internally)

Cooldown periods (per type+ticker combo):
  entry_signal:     4 h  — don't re-alert same ticker in same session
  stop_approaching: 1 h  — re-check every hour max
  stop_hit:         0    — always send immediately
  target_1_hit:     0    — always send immediately
  target_2_hit:     0    — always send immediately
  earnings_warning: 24 h — once per day per ticker
  daily_summary:    12 h — once per half-day
  morning_briefing: 12 h — once per half-day
  scan_complete:    4 h  — max once per session
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.alert import Alert

settings = get_settings()

# ── Cooldown map (seconds per alert type) ─────────────────────────────────────

COOLDOWNS: dict[str, int] = {
    "entry_signal":     4 * 3600,
    "stop_approaching": 1 * 3600,
    "stop_hit":         0,
    "target_1_hit":     0,
    "target_2_hit":     0,
    "earnings_warning": 24 * 3600,
    "daily_summary":    12 * 3600,
    "morning_briefing": 12 * 3600,
    "scan_complete":    4 * 3600,
}

_TELEGRAM_BASE = "https://api.telegram.org/bot{token}/sendMessage"


# ── Low-level send ─────────────────────────────────────────────────────────────

async def send_message(text: str) -> bool:
    """
    Send a plain text (Markdown V2) message to the configured chat.
    Returns True on success, False on failure (never raises).
    """
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        return False

    url = _TELEGRAM_BASE.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False


# ── Cooldown check ─────────────────────────────────────────────────────────────

async def _is_on_cooldown(db: AsyncSession, alert_type: str, ticker: str | None) -> bool:
    """Return True if a similar alert was sent within the cooldown window."""
    cooldown_secs = COOLDOWNS.get(alert_type, 0)
    if cooldown_secs == 0:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=cooldown_secs)
    stmt = (
        select(Alert)
        .where(Alert.type == alert_type)
        .where(Alert.sent_at >= cutoff)
    )
    if ticker:
        stmt = stmt.where(Alert.ticker == ticker)

    result = await db.execute(stmt.limit(1))
    return result.scalar_one_or_none() is not None


# ── Persist + send ────────────────────────────────────────────────────────────

async def send_alert(
    db: AsyncSession,
    alert_type: str,
    message: str,
    ticker: str | None = None,
    priority: str = "medium",
    skip_cooldown: bool = False,
) -> bool:
    """
    Check cooldown → save to alerts table → send via Telegram.
    Returns True if message was sent (not on cooldown).
    """
    if not skip_cooldown and await _is_on_cooldown(db, alert_type, ticker):
        return False

    # Persist alert record
    alert = Alert(
        type=alert_type,
        ticker=ticker,
        priority=priority,
        message=message,
        sent_via="telegram",
    )
    db.add(alert)
    await db.commit()

    # Send via Telegram
    await send_message(message)
    return True


# ── Formatters (one per alert type) ───────────────────────────────────────────

def fmt_entry_signal(
    ticker: str,
    signal_type: str,
    entry_low: float,
    entry_high: float,
    stop_loss: float,
    target_1: float,
    target_2: float,
    rr: float,
    signal_strength: float,
    exchange: str = "",
    sector: str = "",
    fx_cost: float = 0.0,
) -> str:
    fx_note = f"\n⚠️ FX cost: {fx_cost:.1f}% round-trip" if fx_cost > 0 else ""
    exch_note = f" ({exchange})" if exchange else ""
    sector_note = f" • {sector}" if sector else ""
    return (
        f"🎯 <b>Entry Signal: {ticker}{exch_note}</b>{sector_note}\n"
        f"Signal: <b>{signal_type}</b>  Score: {signal_strength:.0%}\n"
        f"\n"
        f"Entry zone: <b>${entry_low:.2f} – ${entry_high:.2f}</b>\n"
        f"Stop loss:  <b>${stop_loss:.2f}</b>\n"
        f"Target 1:   <b>${target_1:.2f}</b>\n"
        f"Target 2:   <b>${target_2:.2f}</b>\n"
        f"R/R:        <b>{rr:.1f}:1</b>"
        f"{fx_note}"
    )


def fmt_stop_approaching(ticker: str, current_price: float, stop_price: float, pct_away: float) -> str:
    return (
        f"⚠️ <b>Stop Approaching: {ticker}</b>\n"
        f"Current: <b>${current_price:.2f}</b>  Stop: <b>${stop_price:.2f}</b>\n"
        f"<b>{pct_away:.1f}%</b> away from stop loss"
    )


def fmt_stop_hit(ticker: str, exit_price: float, stop_price: float, pnl: float | None = None) -> str:
    pnl_note = f"\nP&L: <b>{'−' if pnl and pnl < 0 else '+'}{abs(pnl):.2f}</b>" if pnl is not None else ""
    return (
        f"🛑 <b>Stop Hit: {ticker}</b>\n"
        f"Exit: <b>${exit_price:.2f}</b>  Stop was: <b>${stop_price:.2f}</b>"
        f"{pnl_note}"
    )


def fmt_target_hit(ticker: str, target_num: int, price: float, pnl: float | None = None) -> str:
    emoji = "✅" if target_num == 1 else "🏆"
    pnl_note = f"\nP&L: <b>+{pnl:.2f}</b>" if pnl is not None else ""
    return (
        f"{emoji} <b>Target {target_num} Hit: {ticker}</b>\n"
        f"Price: <b>${price:.2f}</b>"
        f"{pnl_note}"
    )


def fmt_earnings_warning(ticker: str, days_away: int, earnings_date: str, in_blackout: bool) -> str:
    flag = "🚨 <b>BLACKOUT</b> — " if in_blackout else ""
    return (
        f"📅 <b>Earnings Warning: {ticker}</b>\n"
        f"{flag}Earnings in <b>{days_away}d</b> ({earnings_date})\n"
        f"{'No new positions allowed — within 5-day blackout.' if in_blackout else 'Review before entering new position.'}"
    )


def fmt_morning_briefing(candidates: list[dict], scan_date: str, total_scanned: int) -> str:
    if not candidates:
        return (
            f"🌅 <b>Morning Briefing — {scan_date}</b>\n"
            f"Scanned {total_scanned} tickers. No candidates found today."
        )

    lines = [f"🌅 <b>Morning Briefing — {scan_date}</b>", f"Scanned {total_scanned} tickers — <b>{len(candidates)} candidates</b>\n"]
    for i, c in enumerate(candidates[:5], 1):
        ticker = c.get("ticker", "")
        signal = c.get("signal_type", "")
        score = c.get("signal_strength", 0.0)
        price = c.get("current_price")
        price_str = f"${price:.2f}" if price else "—"
        lines.append(f"{i}. <b>{ticker}</b> {price_str}  {signal}  {score:.0%}")

    if len(candidates) > 5:
        lines.append(f"\n…and {len(candidates) - 5} more")
    return "\n".join(lines)


def fmt_daily_summary(
    portfolio_value: float,
    daily_change: float,
    daily_change_pct: float,
    active_trades: int,
    candidates_today: int,
    alerts_today: int,
) -> str:
    sign = "+" if daily_change >= 0 else ""
    change_emoji = "📈" if daily_change >= 0 else "📉"
    return (
        f"{change_emoji} <b>Daily Summary</b>\n"
        f"\n"
        f"Portfolio: <b>${portfolio_value:,.0f} CAD</b>\n"
        f"Today:     <b>{sign}${daily_change:,.2f} ({sign}{daily_change_pct:.2f}%)</b>\n"
        f"\n"
        f"Active trades:  {active_trades}\n"
        f"Scan candidates: {candidates_today}\n"
        f"Alerts sent:     {alerts_today}"
    )


def fmt_macro_update(overnight_rate: str, usd_cad: str, wti: str, gold: str) -> str:
    return (
        f"🏦 <b>Macro Update</b>\n"
        f"BoC Overnight: <b>{overnight_rate}</b>\n"
        f"USD/CAD:       <b>{usd_cad}</b>\n"
        f"WTI Oil:       <b>{wti}</b>\n"
        f"Gold:          <b>{gold}</b>"
    )
