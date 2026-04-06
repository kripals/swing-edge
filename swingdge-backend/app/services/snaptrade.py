"""
SnapTrade client — read-only portfolio sync with Wealthsimple.

Uses the official snaptrade-python-sdk which handles HMAC-SHA256 signing.

Setup flow (done once):
  1. POST /api/snaptrade/register → get userId + userSecret
  2. Add both to Render env vars and redeploy
  3. GET /api/snaptrade/connect → get OAuth URL
  4. Open URL in browser → log into Wealthsimple → grant access
  5. portfolio-sync trigger pulls holdings/balances automatically
"""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

settings = get_settings()


def _client():
    from snaptrade_client import SnapTrade
    return SnapTrade(
        consumer_key=settings.snaptrade_consumer_key,
        client_id=settings.snaptrade_client_id,
    )


# ── Registration (run once during setup) ─────────────────────────────────────

async def register_user() -> dict:
    """
    Register as a SnapTrade user. Run once during initial setup.
    Returns userId and userSecret — save both to Render env vars.
    """
    st = _client()
    user_id = settings.snaptrade_user_id or str(uuid.uuid4())
    response = st.authentication.register_snap_trade_user(body={"userId": user_id})
    return response.body


async def get_connection_link(redirect_uri: str) -> str:
    """
    Get the Wealthsimple OAuth URL. Open in browser to link the account.
    """
    st = _client()
    response = st.authentication.login_snap_trade_user(
        query_params={
            "userId": settings.snaptrade_user_id,
            "userSecret": settings.snaptrade_user_secret_encrypted,
        },
        body={
            "broker": "WEALTHSIMPLETRADE",
            "immediateRedirect": True,
            "customRedirect": redirect_uri,
        },
    )
    return response.body.get("redirectURI", "")


# ── Portfolio data ────────────────────────────────────────────────────────────

async def get_accounts() -> list[dict]:
    """Returns all linked brokerage accounts."""
    st = _client()
    response = st.account_information.list_user_accounts(
        query_params={
            "userId": settings.snaptrade_user_id,
            "userSecret": settings.snaptrade_user_secret_encrypted,
        }
    )
    data = response.body
    if not isinstance(data, list):
        return []
    return data


async def get_all_positions() -> list[dict]:
    """Returns all positions across all linked accounts."""
    st = _client()
    response = st.account_information.get_all_user_holdings(
        query_params={
            "userId": settings.snaptrade_user_id,
            "userSecret": settings.snaptrade_user_secret_encrypted,
        }
    )
    data = response.body
    if not isinstance(data, list):
        return []

    positions = []
    for account_data in data:
        account_id = account_data.get("account", {}).get("id")
        for pos in account_data.get("positions", []):
            symbol_info = pos.get("symbol", {})
            positions.append({
                "snaptrade_account_id": account_id,
                "ticker": _clean_ticker(symbol_info.get("symbol", "")),
                "exchange": symbol_info.get("exchange", {}).get("code", ""),
                "currency": symbol_info.get("currency", {}).get("code", "CAD"),
                "shares": float(pos.get("units", 0) or 0),
                "avg_cost": float(pos.get("average_purchase_price", 0) or 0),
                "current_price": float(pos.get("price", 0) or 0),
                "open_pnl": float(pos.get("open_pnl", 0) or 0),
            })
    return positions


async def get_balances() -> dict[str, float]:
    """Returns {snaptrade_account_id: total_balance_cad} for all accounts."""
    st = _client()
    response = st.account_information.get_user_account_balance(
        query_params={
            "userId": settings.snaptrade_user_id,
            "userSecret": settings.snaptrade_user_secret_encrypted,
        }
    )
    data = response.body
    balances: dict[str, float] = {}
    if not isinstance(data, list):
        return balances
    for item in data:
        acc_id = item.get("account", {}).get("id")
        total = item.get("total", {})
        amount = float(total.get("amount", 0) or 0)
        if acc_id:
            balances[acc_id] = amount
    return balances


# ── DB Sync ───────────────────────────────────────────────────────────────────

async def sync_portfolio(db: AsyncSession) -> dict[str, int]:
    """
    Full portfolio sync: fetch from SnapTrade, upsert into holdings + accounts tables.
    """
    accounts_updated = 0
    positions_updated = 0

    balances = await get_balances()
    for snaptrade_id, balance in balances.items():
        result = await db.execute(
            text("""
                UPDATE accounts SET balance = :balance, updated_at = NOW()
                WHERE snaptrade_account_id = :snaptrade_id
                RETURNING id
            """),
            {"balance": balance, "snaptrade_id": snaptrade_id},
        )
        if result.rowcount:
            accounts_updated += 1

    positions = await get_all_positions()
    for pos in positions:
        result = await db.execute(
            text("SELECT id, has_usd_account FROM accounts WHERE snaptrade_account_id = :sid"),
            {"sid": pos["snaptrade_account_id"]},
        )
        account_row = result.fetchone()
        if not account_row:
            continue
        account_id, has_usd_account = account_row
        has_fx = pos["currency"] == "USD" and not has_usd_account

        await db.execute(
            text("""
                INSERT INTO holdings (account_id, ticker, exchange, shares, avg_cost, currency, current_price, has_fx_cost, updated_at)
                VALUES (:account_id, :ticker, :exchange, :shares, :avg_cost, :currency, :current_price, :has_fx, NOW())
                ON CONFLICT (account_id, ticker) DO UPDATE
                    SET shares = EXCLUDED.shares,
                        avg_cost = EXCLUDED.avg_cost,
                        current_price = EXCLUDED.current_price,
                        has_fx_cost = EXCLUDED.has_fx_cost,
                        updated_at = NOW()
            """),
            {
                "account_id": account_id,
                "ticker": pos["ticker"],
                "exchange": pos["exchange"],
                "shares": pos["shares"],
                "avg_cost": pos["avg_cost"],
                "currency": pos["currency"],
                "current_price": pos["current_price"],
                "has_fx": has_fx,
            },
        )
        positions_updated += 1

    await db.commit()
    return {"accounts_updated": accounts_updated, "positions_updated": positions_updated}


def _clean_ticker(raw: str) -> str:
    """Normalise SnapTrade ticker to our format (e.g. 'SU.TO' stays as-is)."""
    return raw.strip().upper()
