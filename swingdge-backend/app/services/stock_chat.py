"""
AI Stock Chat service — Claude-powered portfolio advisor chat.

Two context modes:
  portfolio  — assembles all holdings + advisor results + macro data
  ticker     — single-ticker deep dive (indicators, earnings, news, fundamentals)

Model: claude-haiku-4-5-20251001 (cheapest, ~$0.001/message)
Max tokens: 800 (keeps responses concise and costs low)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_SYSTEM_PROMPT = (
    "You are a personal stock advisor for a Canadian swing trader using Wealthsimple TFSA accounts. "
    "You have access to their real portfolio data, live technical indicators, and holdings. "
    "Give concise, actionable advice. Always cite the key metrics (RSI, P&L%, SMA position) when relevant. "
    "Never speculate beyond the data provided. Keep replies under 200 words. "
    "When a holding is flagged SELL or WATCH by the advisor, explain why clearly. "
    "FX note: US stocks cost 3% round-trip in FX fees via Wealthsimple — always factor this into advice."
)


@dataclass
class ChatResponse:
    reply: str
    ticker: str | None
    context_used: str  # "portfolio" | "ticker" | "general"


async def build_portfolio_context(db: AsyncSession) -> str:
    """
    Assemble a compact portfolio context string for Claude.
    Includes all holdings, advisor actions, key indicators, and macro data.
    Kept under ~3000 tokens.
    """
    from app.services import advisor as advisor_svc
    from app.services import cache as cache_svc

    lines: list[str] = ["=== PORTFOLIO CONTEXT ===\n"]

    # Holdings + advisor results
    try:
        results = await advisor_svc.analyze_holdings(db)
        if results:
            lines.append("HOLDINGS & ADVISOR RECOMMENDATIONS:")
            for r in results:
                fx_note = " (FX-adj)" if r.has_fx_cost else ""
                earn_note = f" ⚡ Earnings in {r.earnings_days_away}d" if r.earnings_days_away is not None and r.earnings_days_away <= 7 else ""
                rsi_str = f"RSI {r.rsi_14:.0f}" if r.rsi_14 is not None else "RSI n/a"
                sma_str = ("above" if r.above_sma_50 else "below") + " SMA-50" if r.above_sma_50 is not None else "SMA-50 n/a"
                macd_str = f"MACD {'↑' if r.macd_histogram and r.macd_histogram >= 0 else '↓'}" if r.macd_histogram is not None else ""
                adx_str = f"ADX {r.adx_14:.0f}" if r.adx_14 is not None else ""
                price_str = f"${r.current_price:.2f}" if r.current_price else "n/a"

                lines.append(
                    f"  {r.ticker} [{r.account_name}] — {r.action}{earn_note}\n"
                    f"    Price: {price_str}  Cost: ${r.avg_cost:.2f}  Shares: {r.shares:.0f}\n"
                    f"    P&L: {r.fx_adjusted_pnl_pct:+.1f}%{fx_note} (raw: {r.unrealized_pnl_pct:+.1f}%)\n"
                    f"    {rsi_str}  {sma_str}  {macd_str}  {adx_str}\n"
                    f"    Reason: {r.reason}"
                )
        else:
            lines.append("No holdings found.")
    except Exception as e:
        logger.warning("portfolio context: advisor failed: %s", e)
        lines.append("Holdings data unavailable.")

    # Macro snapshot
    try:
        usd_cad = await cache_svc.cache_get(db, cache_svc.macro_key("USD_CAD"))
        boc = await cache_svc.cache_get(db, cache_svc.macro_key("BOC_OVERNIGHT"))
        wti = await cache_svc.cache_get(db, cache_svc.macro_key("WTI_OIL"))
        gold = await cache_svc.cache_get(db, cache_svc.macro_key("GOLD"))

        macro_parts = []
        if usd_cad:
            macro_parts.append(f"USD/CAD: {float(usd_cad):.4f}")
        if boc:
            macro_parts.append(f"BoC rate: {boc}%")
        if wti:
            macro_parts.append(f"WTI: ${float(wti):.2f}")
        if gold:
            macro_parts.append(f"Gold: ${float(gold):.2f}")

        if macro_parts:
            lines.append(f"\nMACRO: {' | '.join(macro_parts)}")
    except Exception:
        pass

    return "\n".join(lines)


async def build_ticker_context(db: AsyncSession, ticker: str) -> str:
    """
    Assemble a single-ticker deep-dive context string for Claude.
    Includes indicators, earnings, news sentiment, fundamentals, and any open trade plan.
    Kept under ~2000 tokens.
    """
    from app.services import twelve_data, indicators as ind_svc
    from app.services import earnings as earn_svc
    from app.services import fmp as fmp_svc
    from app.services import news as news_svc
    from app.models.trade_plan import TradePlan
    from app.models.holding import Holding
    from sqlalchemy import select

    lines: list[str] = [f"=== TICKER CONTEXT: {ticker} ===\n"]

    # Indicators
    try:
        indics = await twelve_data.get_indicators(db, ticker)
        candles = await twelve_data.get_daily_ohlcv(db, ticker, output_size=60)
        extras = ind_svc.compute_extras(candles) if candles else {}

        quote = await twelve_data.get_batch_quotes(db, [ticker])
        price = quote.get(ticker, {}).get("price")

        rsi = indics.get("rsi_14")
        sma_50 = indics.get("sma_50")
        sma_200 = indics.get("sma_200")
        macd_hist = indics.get("macd_histogram")
        adx = indics.get("adx_14")
        atr = indics.get("atr_14")
        vol_ratio = extras.get("volume_ratio")
        high_52w = extras.get("high_52w")

        above_50 = (float(price) > float(sma_50)) if price and sma_50 else None
        above_200 = (float(price) > float(sma_200)) if price and sma_200 else None

        lines.append("TECHNICALS:")
        if price:
            lines.append(f"  Price: ${float(price):.2f}")
        if rsi is not None:
            lines.append(f"  RSI-14: {float(rsi):.1f} ({'overbought >70' if float(rsi) > 70 else 'oversold <30' if float(rsi) < 30 else 'neutral'})")
        if sma_50 is not None:
            lines.append(f"  SMA-50: ${float(sma_50):.2f} ({'above' if above_50 else 'below'})")
        if sma_200 is not None:
            lines.append(f"  SMA-200: ${float(sma_200):.2f} ({'above' if above_200 else 'below'})")
        if macd_hist is not None:
            lines.append(f"  MACD histogram: {float(macd_hist):.4f} ({'bullish' if float(macd_hist) >= 0 else 'bearish'})")
        if adx is not None:
            lines.append(f"  ADX-14: {float(adx):.1f} ({'trending' if float(adx) >= 25 else 'weak trend'})")
        if atr is not None:
            lines.append(f"  ATR-14: {float(atr):.2f}")
        if vol_ratio is not None:
            lines.append(f"  Volume ratio: {float(vol_ratio):.2f}x avg")
        if high_52w is not None:
            lines.append(f"  52-week high: ${float(high_52w):.2f}")
    except Exception as e:
        logger.warning("ticker context: indicators failed for %s: %s", ticker, e)
        lines.append("  Indicator data unavailable.")

    # Earnings
    try:
        in_blackout, earn_date, days_away = await earn_svc.is_in_blackout(db, ticker)
        lines.append(f"\nEARNINGS:")
        if earn_date:
            lines.append(f"  Next earnings: {earn_date} ({days_away}d away)")
            lines.append(f"  Blackout: {'YES — within 5-day window' if in_blackout else 'No'}")
        else:
            lines.append("  No upcoming earnings date found.")
    except Exception:
        pass

    # News sentiment
    try:
        sentiment_data = await news_svc.get_sentiment(db, ticker)
        if sentiment_data is not None:
            score = float(sentiment_data.get("score", 0.0))
            label = sentiment_data.get("label", "neutral")
            count = sentiment_data.get("article_count", 0)
            lines.append(f"\nNEWS SENTIMENT: {label} (score: {score:.2f}, {count} articles)")
    except Exception:
        pass

    # Fundamentals
    try:
        profile = await fmp_svc.get_profile(db, ticker)
        ratings = await fmp_svc.get_analyst_ratings(db, ticker)
        if profile:
            lines.append(f"\nFUNDAMENTALS:")
            if profile.get("pe_ratio"):
                lines.append(f"  P/E: {profile['pe_ratio']:.1f}")
            if profile.get("eps"):
                lines.append(f"  EPS: {profile['eps']:.2f}")
            if profile.get("beta"):
                lines.append(f"  Beta: {profile['beta']:.2f}")
            if profile.get("market_cap"):
                lines.append(f"  Market cap: ${profile['market_cap']:,.0f}")
            if profile.get("sector"):
                lines.append(f"  Sector: {profile['sector']}")
        if ratings:
            lines.append(f"  Analyst consensus: {ratings.get('consensus', 'N/A')} ({ratings.get('total', 0)} analysts)")
    except Exception:
        pass

    # Holding in portfolio?
    try:
        holding_res = await db.execute(
            select(Holding).where(Holding.ticker == ticker)
        )
        holding = holding_res.scalar_one_or_none()
        if holding:
            raw_pnl = ((float(holding.current_price or holding.avg_cost) - float(holding.avg_cost)) / float(holding.avg_cost) * 100)
            lines.append(f"\nIN YOUR PORTFOLIO:")
            lines.append(f"  Shares: {float(holding.shares):.0f}  Avg cost: ${float(holding.avg_cost):.2f}")
            lines.append(f"  Unrealized P&L: {raw_pnl:+.1f}%")
    except Exception:
        pass

    # Open trade plan?
    try:
        plan_res = await db.execute(
            select(TradePlan).where(
                TradePlan.ticker == ticker,
                TradePlan.status.in_(["pending", "active", "hit_t1"]),
            ).limit(1)
        )
        plan = plan_res.scalar_one_or_none()
        if plan:
            lines.append(f"\nOPEN TRADE PLAN:")
            lines.append(f"  Status: {plan.status}  Signal: {plan.signal_type}")
            lines.append(f"  Entry: ${float(plan.entry_low):.2f}–${float(plan.entry_high):.2f}")
            lines.append(f"  Stop: ${float(plan.stop_loss):.2f}  T1: ${float(plan.target_1):.2f}  T2: ${float(plan.target_2):.2f}")
            lines.append(f"  R/R: {float(plan.risk_reward_ratio):.1f}:1")
    except Exception:
        pass

    return "\n".join(lines)


def _detect_ticker(message: str, known_tickers: set[str]) -> str | None:
    """
    Extract a ticker symbol from the user message by matching against known tickers.
    Matches patterns like NKE, SU.TO, RY.TO — case-insensitive.
    """
    candidates = re.findall(r'\b([A-Z]{1,5}(?:\.TO)?)\b', message.upper())
    for c in candidates:
        if c in known_tickers:
            return c
    return None


async def chat(db: AsyncSession, user_message: str, ticker: str | None = None) -> ChatResponse:
    """
    Main entry point. Builds context, calls Claude, persists to chat_history.
    """
    from app.models.chat_history import ChatHistory
    from app.models.ticker import Ticker as TickerModel
    from sqlalchemy import select
    import anthropic

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured")

    # Resolve ticker — prefer explicit param, then detect from message
    if not ticker:
        ticker_res = await db.execute(select(TickerModel.ticker).where(TickerModel.is_active == True))
        known = {row[0].upper() for row in ticker_res.fetchall()}
        ticker = _detect_ticker(user_message, known)

    # Build context
    if ticker:
        context = await build_ticker_context(db, ticker)
        context_used = "ticker"
    else:
        context = await build_portfolio_context(db)
        context_used = "portfolio"

    # Call Claude
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"{context}\n\nUser question: {user_message}",
            }
        ],
    )
    reply = message.content[0].text

    # Persist to DB
    record = ChatHistory(
        user_message=user_message,
        ai_reply=reply,
        ticker=ticker,
        context_used=context_used,
    )
    db.add(record)
    await db.commit()

    return ChatResponse(reply=reply, ticker=ticker, context_used=context_used)
