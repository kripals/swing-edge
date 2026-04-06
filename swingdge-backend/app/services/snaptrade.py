"""
SnapTrade client — read-only portfolio sync with Wealthsimple.

SnapTrade acts as a broker aggregator. We use it to:
  1. Connect Wealthsimple accounts (OAuth flow — done once in Settings)
  2. Fetch account balances
  3. Fetch current positions (holdings)

We do NOT use SnapTrade for trading — read-only only.

Free tier: 5 broker connections (enough for Kripal TFSA + Sushma TFSA).

Setup flow (manual, done once):
  1. Register user with SnapTrade (POST /snapTrade/registerUser)
  2. Get connection link (POST /snapTrade/login) → redirect user to Wealthsimple OAuth
  3. User logs in and grants access
  4. SnapTrade returns brokerage_authorization_id — store in accounts.snaptrade_account_id
  5. From then on, call /holdings and /balances to sync

NOTE: snaptrade-python-sdk handles request signing (HMAC-SHA256).
"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

settings = get_settings()

_BASE = "https://api.snaptrade.com/api/v1"
_TIMEOUT = 20.0


# ── Request signing ───────────────────────────────────────────────────────────

def _sign_request(path: str, timestamp: str, query_params: str = "") -> str:
    """HMAC-SHA256 signature required by SnapTrade for all requests."""
    message = f"{timestamp}{path}{query_params}"
    return hmac.new(
        settings.snaptrade_consumer_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


def _auth_headers(path: str, query_params: str = "") -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    signature = _sign_request(path, timestamp, query_params)
    return {
        "clientId": settings.snaptrade_client_id,
        "timestamp": timestamp,
        "signature": signature,
        "Content-Type": "application/json",
    }


def _user_params() -> dict[str, str]:
    return {
        "userId": settings.snaptrade_user_id,
        "userSecret": settings.snaptrade_user_secret_encrypted,
    }


async def _get(path: str, extra_params: dict | None = None) -> Any:
    params = _user_params()
    if extra_params:
        params.update(extra_params)
    query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    headers = _auth_headers(path, query_string)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_BASE}{path}", params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def _post(path: str, body: dict) -> Any:
    import json as _json
    body_str = _json.dumps(body, separators=(",", ":"))
    headers = _auth_headers(path, body_str)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{_BASE}{path}", content=body_str, headers=headers)
        resp.raise_for_status()
        return resp.json()


# ── Registration (run once during setup) ─────────────────────────────────────

async def register_user() -> dict:
    """
    Register Kripal as a SnapTrade user. Run once during initial setup.
    Stores userId + userSecret — keep userSecret encrypted in DB.
    """
    body = {
        "userId": settings.snaptrade_user_id or str(uuid.uuid4()),
    }
    return await _post("/snapTrade/registerUser", body)


async def get_connection_link(redirect_uri: str) -> str:
    """
    Get the OAuth URL to send the user to Wealthsimple for account linking.
    Returns the redirect URL string.
    """
    body = {
        "userId": settings.snaptrade_user_id,
        "userSecret": settings.snaptrade_user_secret_encrypted,
        "broker": "WEALTHSIMPLE",
        "immediateRedirect": True,
        "customRedirect": redirect_uri,
    }
    data = await _post("/snapTrade/login", body)
    return data.get("redirectURI", "")


# ── Portfolio Sync ────────────────────────────────────────────────────────────

async def get_accounts() -> list[dict]:
    """
    Returns all linked brokerage accounts with balances.
    [{id, name, number, institution_name, balance: {total: {amount, currency}}}]
    """
    data = await _get("/accounts")
    if not isinstance(data, list):
        return []
    return data


async def get_all_positions() -> list[dict]:
    """
    Returns all positions across all linked accounts.
    [{account_id, symbol, units, price, open_pnl, ...}]
    """
    data = await _get("/holdings")
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
    """
    Returns {snaptrade_account_id: total_balance_cad} for all accounts.
    """
    data = await _get("/accounts/balances")
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
    Full portfolio sync: fetch from SnapTrade, upsert into our holdings + accounts tables.
    Returns {accounts_updated, positions_updated}.
    """
    accounts_updated = 0
    positions_updated = 0

    # Sync balances
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

    # Sync positions
    positions = await get_all_positions()
    for pos in positions:
        # Find our account by SnapTrade ID
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
