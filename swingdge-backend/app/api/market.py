"""
Market intelligence API endpoints.

GET /api/market/macro              — BoC rates + commodity prices
GET /api/market/sectors            — sector ETF performance (rotation tracker)
GET /api/market/quote/:ticker      — rich quote with open/high/low/prev_close
GET /api/market/earnings/:ticker   — next earnings date + history + analyst ratings
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.auth import verify_token
from app.services import market as market_svc

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/macro")
async def get_macro(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Macro snapshot: BoC overnight rate, USD/CAD, CPI, WTI oil, gold,
    natural gas, copper.
    Individual failures return null — macro context is best-effort.
    """
    snap = await market_svc.get_macro(db)
    return {
        "overnight_rate": snap.overnight_rate,
        "usd_cad": snap.usd_cad,
        "cpi": snap.cpi,
        "commodities": {
            "wti_oil": snap.wti_oil,
            "gold": snap.gold,
            "natural_gas": snap.natural_gas,
            "copper": snap.copper,
        },
    }


@router.get("/sectors")
async def get_sectors(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Sector ETF performance sorted by daily % change (best → worst).
    Used for the sector rotation heatmap.
    """
    sectors = await market_svc.get_sectors(db)
    return [
        {
            "ticker": s.ticker,
            "sector": s.sector,
            "name": s.name,
            "price": s.price,
            "change_pct": s.change_pct,
            "volume": s.volume,
        }
        for s in sectors
    ]


@router.get("/quote/{ticker}")
async def get_quote(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Rich quote for a single ticker including OHLC context.
    """
    ticker = ticker.upper()
    return await market_svc.get_quote_with_context(db, ticker)


@router.get("/earnings/{ticker}")
async def get_earnings(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Earnings intelligence for a ticker:
      - Next earnings date + days away
      - Last 4 quarters of EPS actuals vs estimates
      - Analyst buy/hold/sell consensus
      - Company profile (P/E, beta, sector)
    """
    ticker = ticker.upper()
    try:
        result = await market_svc.get_fundamentals(db, ticker)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fundamentals fetch failed: {e}")

    return {
        "ticker": result.ticker,
        "next_earnings_date": result.next_earnings_date,
        "earnings_days_away": result.earnings_days_away,
        "earnings_history": result.earnings_history,
        "analyst_ratings": result.analyst_ratings,
        "profile": result.profile,
    }
