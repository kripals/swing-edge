"""
Portfolio service — P&L calculations, FX cost engine, health checks.

All monetary values are in CAD unless noted.
FX cost rule (Wealthsimple): 1.5% on buy + 1.5% on sell = 3% round-trip for US stocks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import twelve_data, cache as cache_svc

settings = get_settings()


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class HoldingSnapshot:
    id: int
    account_id: int
    account_name: str
    ticker: str
    exchange: str
    shares: float
    avg_cost: float
    currency: str
    current_price: float | None
    sector: str | None
    is_leveraged_etf: bool
    has_fx_cost: bool

    # Computed
    market_value_local: float = 0.0    # in holding currency
    market_value_cad: float = 0.0      # converted to CAD
    cost_basis: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    fx_warning: bool = False
    flags: list[str] = field(default_factory=list)


@dataclass
class AccountSummary:
    id: int
    name: str
    account_type: str
    currency: str
    balance: float
    contribution_room: float | None
    holdings: list[HoldingSnapshot] = field(default_factory=list)
    total_market_value_cad: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_unrealized_pnl_pct: float = 0.0


@dataclass
class PortfolioSummary:
    accounts: list[AccountSummary] = field(default_factory=list)
    total_value_cad: float = 0.0
    total_cost_cad: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_unrealized_pnl_pct: float = 0.0
    daily_change_cad: float = 0.0
    daily_change_pct: float = 0.0
    flags: list[str] = field(default_factory=list)       # portfolio-level warnings
    sector_weights: dict[str, float] = field(default_factory=dict)


# ── FX Cost Engine ────────────────────────────────────────────────────────────

def calculate_fx_cost(
    entry_price: float,
    target_price: float,
    currency: str,
    has_usd_account: bool,
) -> dict[str, float]:
    """
    For a US stock trade, calculate true net gain after Wealthsimple FX costs.
    Returns {gross_gain_pct, fx_cost_pct, net_gain_pct, fx_warning}
    """
    if currency == "CAD" or has_usd_account:
        gross_pct = ((target_price - entry_price) / entry_price) * 100
        return {
            "gross_gain_pct": round(gross_pct, 2),
            "fx_cost_pct": 0.0,
            "net_gain_pct": round(gross_pct, 2),
            "fx_warning": False,
        }

    gross_pct = ((target_price - entry_price) / entry_price) * 100
    fx_cost_pct = settings.fx_round_trip_pct  # 3.0%
    net_pct = gross_pct - fx_cost_pct

    return {
        "gross_gain_pct": round(gross_pct, 2),
        "fx_cost_pct": fx_cost_pct,
        "net_gain_pct": round(net_pct, 2),
        "fx_warning": net_pct < settings.fx_warning_threshold_pct if hasattr(settings, 'fx_warning_threshold_pct') else net_pct < 2.0,
    }


def net_gain_after_fx(
    entry_price: float,
    target_price: float,
    currency: str,
    has_usd_account: bool = False,
) -> float:
    result = calculate_fx_cost(entry_price, target_price, currency, has_usd_account)
    return result["net_gain_pct"]


# ── P&L Calculations ──────────────────────────────────────────────────────────

def compute_holding_pnl(
    shares: float,
    avg_cost: float,
    current_price: float,
    currency: str,
    usd_cad_rate: float = 1.38,  # fallback if live rate unavailable
) -> dict[str, float]:
    """
    Returns {market_value_local, market_value_cad, cost_basis_cad, unrealized_pnl, unrealized_pnl_pct}
    """
    market_value_local = shares * current_price
    cost_basis_local = shares * avg_cost
    unrealized_pnl_local = market_value_local - cost_basis_local
    unrealized_pnl_pct = (unrealized_pnl_local / cost_basis_local * 100) if cost_basis_local else 0.0

    fx = usd_cad_rate if currency == "USD" else 1.0
    market_value_cad = market_value_local * fx
    cost_basis_cad = cost_basis_local * fx
    unrealized_pnl_cad = unrealized_pnl_local * fx

    return {
        "market_value_local": round(market_value_local, 2),
        "market_value_cad": round(market_value_cad, 2),
        "cost_basis_cad": round(cost_basis_cad, 2),
        "unrealized_pnl": round(unrealized_pnl_cad, 2),
        "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
    }


# ── Portfolio Assembly ────────────────────────────────────────────────────────

async def get_portfolio_summary(db: AsyncSession) -> PortfolioSummary:
    """
    Full portfolio snapshot:
    1. Load accounts + holdings from DB
    2. Fetch live prices from Twelve Data
    3. Compute P&L for each holding
    4. Aggregate to account + portfolio level
    5. Run health checks (concentration, leveraged ETFs, FX exposure)
    """
    # 1. Load data
    accounts_result = await db.execute(
        text("SELECT id, name, account_type, currency, balance, contribution_room FROM accounts ORDER BY id")
    )
    accounts_rows = accounts_result.fetchall()

    holdings_result = await db.execute(
        text("""
            SELECT h.id, h.account_id, a.name as account_name, h.ticker, h.exchange,
                   h.shares, h.avg_cost, h.currency, h.current_price, h.sector,
                   h.is_leveraged_etf, h.has_fx_cost
            FROM holdings h
            JOIN accounts a ON a.id = h.account_id
            ORDER BY h.account_id, h.ticker
        """)
    )
    holdings_rows = holdings_result.fetchall()

    if not holdings_rows:
        return PortfolioSummary()

    # 2. Fetch live prices in batch
    tickers = list({row.ticker for row in holdings_rows})
    try:
        live_quotes = await twelve_data.get_batch_quotes(db, tickers)
    except Exception:
        live_quotes = {}

    # Get USD/CAD rate (use cached macro value or fallback)
    usd_cad_cached = await cache_svc.cache_get(db, cache_svc.macro_key("USD_CAD"))
    usd_cad_rate: float = float(usd_cad_cached) if usd_cad_cached else 1.38

    # 3. Build holding snapshots
    holding_map: dict[int, list[HoldingSnapshot]] = {}  # account_id → holdings
    all_holdings: list[HoldingSnapshot] = []

    for row in holdings_rows:
        quote = live_quotes.get(row.ticker, {})
        live_price = quote.get("price") or row.current_price or row.avg_cost

        pnl = compute_holding_pnl(
            shares=float(row.shares),
            avg_cost=float(row.avg_cost),
            current_price=float(live_price),
            currency=row.currency,
            usd_cad_rate=usd_cad_rate,
        )

        flags: list[str] = []
        if row.is_leveraged_etf:
            flags.append("LEVERAGED_ETF")
        if row.has_fx_cost:
            flags.append(f"FX_COST_{settings.fx_round_trip_pct:.0f}PCT")
        if pnl["unrealized_pnl_pct"] <= -20:
            flags.append("LARGE_LOSS")
        if pnl["unrealized_pnl_pct"] >= 50:
            flags.append("CONSIDER_PROFIT_TAKING")

        snap = HoldingSnapshot(
            id=row.id,
            account_id=row.account_id,
            account_name=row.account_name,
            ticker=row.ticker,
            exchange=row.exchange,
            shares=float(row.shares),
            avg_cost=float(row.avg_cost),
            currency=row.currency,
            current_price=live_price,
            sector=row.sector,
            is_leveraged_etf=row.is_leveraged_etf,
            has_fx_cost=row.has_fx_cost,
            market_value_local=pnl["market_value_local"],
            market_value_cad=pnl["market_value_cad"],
            cost_basis=pnl["cost_basis_cad"],
            unrealized_pnl=pnl["unrealized_pnl"],
            unrealized_pnl_pct=pnl["unrealized_pnl_pct"],
            flags=flags,
        )
        holding_map.setdefault(row.account_id, []).append(snap)
        all_holdings.append(snap)

    # 4. Build account summaries
    total_value = 0.0
    total_cost = 0.0
    account_summaries: list[AccountSummary] = []

    for acc_row in accounts_rows:
        acc_holdings = holding_map.get(acc_row.id, [])
        acc_value = sum(h.market_value_cad for h in acc_holdings)
        acc_cost = sum(h.cost_basis for h in acc_holdings)
        acc_pnl = acc_value - acc_cost
        acc_pnl_pct = (acc_pnl / acc_cost * 100) if acc_cost else 0.0

        account_summaries.append(AccountSummary(
            id=acc_row.id,
            name=acc_row.name,
            account_type=acc_row.account_type,
            currency=acc_row.currency,
            balance=float(acc_row.balance or 0),
            contribution_room=float(acc_row.contribution_room) if acc_row.contribution_room else None,
            holdings=acc_holdings,
            total_market_value_cad=round(acc_value, 2),
            total_unrealized_pnl=round(acc_pnl, 2),
            total_unrealized_pnl_pct=round(acc_pnl_pct, 2),
        ))
        total_value += acc_value
        total_cost += acc_cost

    # 5. Portfolio-level health checks
    portfolio_flags: list[str] = []
    sector_weights: dict[str, float] = {}

    if total_value > 0:
        # Sector concentration check
        sector_values: dict[str, float] = {}
        for h in all_holdings:
            if h.sector:
                sector_values[h.sector] = sector_values.get(h.sector, 0) + h.market_value_cad

        for sector, value in sector_values.items():
            weight = (value / total_value) * 100
            sector_weights[sector] = round(weight, 1)
            if weight > settings.max_sector_pct if hasattr(settings, 'max_sector_pct') else weight > 30:
                portfolio_flags.append(f"SECTOR_OVERWEIGHT:{sector}:{weight:.0f}%")

        # Individual position concentration check
        for h in all_holdings:
            if not h.is_leveraged_etf:
                weight = (h.market_value_cad / total_value) * 100
                if weight > 15:
                    portfolio_flags.append(f"POSITION_OVERWEIGHT:{h.ticker}:{weight:.0f}%")

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0

    return PortfolioSummary(
        accounts=account_summaries,
        total_value_cad=round(total_value, 2),
        total_cost_cad=round(total_cost, 2),
        total_unrealized_pnl=round(total_pnl, 2),
        total_unrealized_pnl_pct=round(total_pnl_pct, 2),
        flags=portfolio_flags,
        sector_weights=sector_weights,
    )
