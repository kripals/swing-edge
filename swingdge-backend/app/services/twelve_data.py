"""
Twelve Data API client — primary source for OHLCV + technical indicators.

Free tier: 800 credits/day, 8 credits/minute.
Batch support: up to 120 symbols per request (counts as 1 rate-limit slot but N credits).

Key design decisions:
- Circuit breaker: after 3 consecutive failures, stop hitting the API for 5 minutes
- Batch quotes: fetch all holdings in one call instead of N separate calls
- Cache: check cache before every API call (daily OHLCV TTL = 20h)
- TSX tickers: use "SU:TSX" format (Twelve Data canonical for batch)
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import cache as cache_svc

settings = get_settings()

_BASE = "https://api.twelvedata.com"
_TIMEOUT = 15.0

# ── Rate Limiter (8 calls/minute free tier) ───────────────────────────────────

class _RateLimiter:
    """Token bucket: max 8 calls per 60s window."""
    def __init__(self, max_calls: int = 8, period: float = 60.0):
        self._max = max_calls
        self._period = period
        self._timestamps: deque = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # Drop timestamps older than the window
            while self._timestamps and now - self._timestamps[0] >= self._period:
                self._timestamps.popleft()
            if len(self._timestamps) >= self._max:
                sleep_for = self._period - (now - self._timestamps[0])
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
            self._timestamps.append(time.monotonic())


_rate_limiter = _RateLimiter(max_calls=8, period=60.0)


# ── Circuit Breaker ───────────────────────────────────────────────────────────

class _CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_seconds: int = 300):
        self._failures = 0
        self._threshold = failure_threshold
        self._open_until: float = 0.0

    @property
    def is_open(self) -> bool:
        if self._open_until and time.time() < self._open_until:
            return True
        if self._open_until and time.time() >= self._open_until:
            self._failures = 0
            self._open_until = 0.0
        return False

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._open_until = time.time() + 300  # 5 min cooldown
            self._failures = 0

    def record_success(self) -> None:
        self._failures = 0


_circuit = _CircuitBreaker()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tsx_symbol(ticker: str) -> str:
    """Convert 'SU.TO' → 'SU:TSX' for Twelve Data batch API."""
    if ticker.endswith(".TO"):
        return ticker[:-3] + ":TSX"
    return ticker


async def _get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    if _circuit.is_open:
        raise RuntimeError("Twelve Data circuit breaker is open — too many recent failures")
    await _rate_limiter.acquire()
    params["apikey"] = settings.twelve_data_key
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(f"{_BASE}/{endpoint}", params=params)
            resp.raise_for_status()
            data = resp.json()
            # Twelve Data signals errors in the response body with status != "ok"
            if isinstance(data, dict) and data.get("status") == "error":
                raise ValueError(f"Twelve Data error: {data.get('message')}")
            _circuit.record_success()
            return data
        except Exception as exc:
            _circuit.record_failure()
            raise


# ── Public API ────────────────────────────────────────────────────────────────

async def get_batch_quotes(
    db: AsyncSession,
    tickers: list[str],
) -> dict[str, dict]:
    """
    Fetch real-time quotes for up to 120 tickers in one API call.
    Returns {ticker: {price, change, change_pct, volume, ...}}
    Uses 2-min in-memory TTL (no PostgreSQL persistence for intraday quotes).
    Falls back to Alpha Vantage individually if Twelve Data circuit is open.
    """
    import logging
    _log = logging.getLogger(__name__)

    results: dict[str, dict] = {}
    uncached: list[str] = []

    for ticker in tickers:
        cached = await cache_svc.cache_get(db, cache_svc.quote_key(ticker), memory_only=True)
        if cached:
            results[ticker] = cached
        else:
            uncached.append(ticker)

    if not uncached:
        return results

    # ── Try Twelve Data batch ─────────────────────────────────────────────────
    td_failed = False
    if not _circuit.is_open:
        try:
            symbols = ",".join(_tsx_symbol(t) for t in uncached)
            data = await _get("quote", {"symbol": symbols})

            if len(uncached) == 1:
                ticker = uncached[0]
                quote = _normalise_quote(data, ticker)
                results[ticker] = quote
                cache_svc._mem_set(cache_svc.quote_key(ticker), quote, cache_svc.TTL.INTRADAY_QUOTE)
            else:
                for ticker in uncached:
                    symbol = _tsx_symbol(ticker)
                    raw = data.get(symbol, {})
                    if raw:
                        quote = _normalise_quote(raw, ticker)
                        results[ticker] = quote
                        cache_svc._mem_set(cache_svc.quote_key(ticker), quote, cache_svc.TTL.INTRADAY_QUOTE)
        except Exception as exc:
            _log.warning("Twelve Data batch quote failed (%s) — falling back to Alpha Vantage", exc)
            td_failed = True
    else:
        _log.warning("Twelve Data circuit open — using Alpha Vantage fallback for quotes")
        td_failed = True

    # ── Alpha Vantage fallback for any tickers still missing ─────────────────
    if td_failed:
        from app.services import alpha_vantage as av
        still_missing = [t for t in uncached if t not in results]
        for ticker in still_missing:
            try:
                price = await av.get_quote_backup(db, ticker)
                if price is not None:
                    quote = {"ticker": ticker, "price": price, "open": None, "high": None,
                             "low": None, "volume": None, "change": None, "change_pct": None,
                             "is_market_open": False, "timestamp": None}
                    results[ticker] = quote
                    cache_svc._mem_set(cache_svc.quote_key(ticker), quote, cache_svc.TTL.INTRADAY_QUOTE)
            except Exception as av_exc:
                _log.warning("Alpha Vantage fallback failed for %s: %s", ticker, av_exc)

    return results


async def get_daily_ohlcv(
    db: AsyncSession,
    ticker: str,
    output_size: int = 100,
) -> list[dict]:
    """
    Fetch daily OHLCV candles (last N days).
    Cached for 20h in PostgreSQL — expensive call, don't repeat daily.
    """
    key = cache_svc.ohlcv_key(ticker)
    cached = await cache_svc.cache_get(db, key)
    if cached:
        return cached

    symbol = _tsx_symbol(ticker)
    data = await _get("time_series", {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": output_size,
        "timezone": "America/New_York",
    })

    candles = data.get("values", [])
    await cache_svc.cache_set(db, key, candles, cache_svc.TTL.DAILY_OHLCV, provider="twelve_data")
    return candles


async def get_indicators(
    db: AsyncSession,
    ticker: str,
) -> dict[str, Any]:
    """
    Fetch all required technical indicators for one ticker in parallel API calls.
    Cached 20h in PostgreSQL.

    Returns: {ema_9, ema_21, sma_50, sma_200, rsi_14, macd, macd_signal, macd_histogram,
              bb_upper, bb_middle, bb_lower, atr_14}
    Note: VWAP + volume_ratio + relative_strength are computed locally from OHLCV.
    """
    key = cache_svc.indicators_key(ticker)
    cached = await cache_svc.cache_get(db, key)
    if cached:
        return cached

    symbol = _tsx_symbol(ticker)

    # Twelve Data supports fetching multiple indicators per call via the complex_data endpoint
    # but on free tier we batch indicator requests as separate calls
    # Each call below uses 1 API credit

    async def fetch(indicator: str, params: dict) -> tuple[str, Any]:
        p = {"symbol": symbol, "interval": "1day", "outputsize": 1, **params}
        data = await _get(indicator, p)
        values = data.get("values", [{}])
        return indicator, values[0] if values else {}

    tasks = [
        fetch("ema",  {"time_period": 9}),
        fetch("ema",  {"time_period": 21}),
        fetch("sma",  {"time_period": 50}),
        fetch("sma",  {"time_period": 200}),
        fetch("rsi",  {"time_period": 14}),
        fetch("macd", {"fast_period": 12, "slow_period": 26, "signal_period": 9}),
        fetch("bbands", {"time_period": 20, "sd": 2}),
        fetch("atr",  {"time_period": 14}),
    ]

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    indicators: dict[str, Any] = {}
    for i, result in enumerate(raw_results):
        if isinstance(result, Exception):
            continue
        _, values = result
        # Map to our canonical names
        if i == 0:
            indicators["ema_9"] = _float(values.get("ema"))
        elif i == 1:
            indicators["ema_21"] = _float(values.get("ema"))
        elif i == 2:
            indicators["sma_50"] = _float(values.get("sma"))
        elif i == 3:
            indicators["sma_200"] = _float(values.get("sma"))
        elif i == 4:
            indicators["rsi_14"] = _float(values.get("rsi"))
        elif i == 5:
            indicators["macd"] = _float(values.get("macd"))
            indicators["macd_signal"] = _float(values.get("macd_signal"))
            indicators["macd_histogram"] = _float(values.get("macd_hist"))
        elif i == 6:
            indicators["bb_upper"] = _float(values.get("upper_band"))
            indicators["bb_middle"] = _float(values.get("middle_band"))
            indicators["bb_lower"] = _float(values.get("lower_band"))
        elif i == 7:
            indicators["atr_14"] = _float(values.get("atr"))

    await cache_svc.cache_set(db, key, indicators, cache_svc.TTL.INDICATORS, provider="twelve_data")
    return indicators


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalise_quote(raw: dict, ticker: str) -> dict:
    return {
        "ticker": ticker,
        "price": _float(raw.get("close") or raw.get("price")),
        "open": _float(raw.get("open")),
        "high": _float(raw.get("high")),
        "low": _float(raw.get("low")),
        "volume": _int(raw.get("volume")),
        "change": _float(raw.get("change")),
        "change_pct": _float(raw.get("percent_change")),
        "is_market_open": raw.get("is_market_open", False),
        "timestamp": raw.get("datetime") or raw.get("timestamp"),
    }


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
