# SwingEdge — Bug Fixes & Reliability

Tracked issues, ordered by priority. Check off each item as fixed.

---

## Critical

### [x] ~~earnings-check calls a function that doesn't exist — always crashes~~ FIXED
**File:** `swingdge-backend/app/api/triggers.py:398`
Now correctly calls `earn_svc.is_in_blackout(db, ticker)`.

---

### [x] ~~Rules key mismatches — settings changes have no effect on scanner or trade plans~~ FIXED
**File:** `swingdge-backend/app/services/rules.py`
All 8 key strings now match `scripts/seed.py` exactly.

---

### [x] ~~macro-update trigger crashes — wti_oil and gold formatted as floats but are dicts~~ FIXED
**File:** `swingdge-backend/app/api/triggers.py:357`
Now correctly accesses `macro.wti_oil['value']` and `macro.gold['value']`.

---

### [x] ~~price-check uses wrong quote key — stop/target alerts never fire~~ FIXED
**File:** `swingdge-backend/app/api/triggers.py:198`
Now correctly uses `q.get("price")` and `q["price"]`.

---

### [x] ~~Scan results deleted before new ones are inserted — data loss on failure~~ FIXED
**File:** `swingdge-backend/app/api/triggers.py:110`
Wrapped in `async with db.begin()` — delete + insert are now one atomic transaction.

---

## High

### [x] ~~Sector change percentages always None — wrong quote key in market.py~~ FIXED
**Files:** `swingdge-backend/app/services/market.py:142` and `market.py:204`
Both now use `q.get("change_pct")`.

---

### [x] ~~`/health` endpoint doesn't check the database~~ FIXED
**File:** `swingdge-backend/app/main.py:95`
Now runs `SELECT 1` and returns 503 if it fails.

---

### [x] ~~daily-summary sends total return % instead of today's daily change %~~ FIXED
**Files:** `swingdge-backend/app/api/triggers.py:297`, `app/services/telegram.py`
Renamed variables to `total_pnl` / `total_pnl_pct`. `fmt_daily_summary` now labels the
figure "Unrealized P&L" — honest since no previous-day snapshots are stored.

---

### [x] ~~Scanner volume filter skips illiquid stocks when volume_ratio is None~~ FIXED
**File:** `swingdge-backend/app/services/scanner.py:154`
Volume check now runs unconditionally before `volume_ratio` is read.

---

## Medium

### [x] ~~RSI_REVERSAL and RSI_PULLBACK always co-fire — inflated COMBO signals~~ FIXED
**File:** `swingdge-backend/app/services/scanner.py:215`
RSI_REVERSAL now requires `not above_sma_50` — it's a distinct bottoming signal for stocks
not yet in a confirmed uptrend. RSI_PULLBACK covers the above-SMA50 case. They can no longer
fire simultaneously.

---

### [x] ~~EMA_CROSSOVER fires on stale state, not actual crossing~~ FIXED
**Files:** `swingdge-backend/app/services/scanner.py`, `app/services/indicators.py`
`compute_extras()` now computes `ema_9_yesterday` and `ema_21_yesterday` from OHLCV candles.
EMA_CROSSOVER only fires when `ema9_yesterday <= ema21_yesterday` (actual cross today).
Falls back to a 2% gap heuristic if yesterday's values are unavailable.

---

### [x] ~~MACD_CROSSOVER fires on noise — no minimum threshold~~ FIXED
**File:** `swingdge-backend/app/services/scanner.py:220`
Now requires `macd_hist > price * 0.005` (0.5% of price minimum). Filters out histogram
values like +0.0001 that flip negative the next bar on choppy stocks.

---

### [x] ~~No API quota tracking — silent failures when daily limit is hit~~ FIXED
**Files:** `swingdge-backend/app/services/twelve_data.py`, `fmp.py`
In-memory counter per provider, resets at midnight UTC. Sends a Telegram warning at 80% usage
(640/800 for Twelve Data, 200/250 for FMP). `alpha_vantage.py` already had a hard 25-call guard.

---

### [x] ~~Only morning-scan has a cold-start wake step — other triggers time out on cold Render~~ FIXED
**File:** `.github/workflows/market-monitor.yml`
Every job now has a 3-retry Wake Render step that polls `/health` before firing its trigger curl.

---

## Low

### [x] ~~No Telegram alert when a scheduled GitHub Actions job fails~~ FIXED
**File:** `.github/workflows/market-monitor.yml`
Every job now has a `Notify on failure` step that posts directly to the Telegram Bot API
on any non-2xx response. Requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` GitHub secrets.

---

### [x] ~~Market holiday guard missing in price-check~~ FIXED
**Files:** `swingdge-backend/app/utils/market_calendar.py` (new), `app/api/triggers.py`
`is_market_open()` checks weekends + hardcoded TSX/NYSE holidays for 2025–2026.
Price-check returns early with "Market closed today" if the market is closed. Fails open
for years not in the holiday list so future years don't silently block price-checks.

---

### [x] ~~Scanner.vue ticker count is hardcoded to 56~~ FIXED
**File:** `swingdge-frontend/src/views/Scanner.vue`
`tickerCount` is now a `ref(56)` updated from `data.total_tickers` returned by the scan endpoint.

---

### [x] ~~dotInterval not cleared on component unmount in Dashboard.vue~~ FIXED
**File:** `swingdge-frontend/src/views/Dashboard.vue:136`
`onUnmounted(() => clearInterval(dotInterval))` is already present.

---

### [x] ~~Circuit breaker state lost on every Render cold start~~ FIXED
**File:** `swingdge-backend/app/services/twelve_data.py`
Circuit state persisted to `api_cache` table (10 min TTL) whenever the circuit opens
(`_circuit_dirty` flag). Restored from DB on the first call after cold start via
`restore_circuit_state(db)`, called at the top of all three public API functions.
`_circuit_restored` guard ensures restore only runs once per process lifetime.

---

### [x] ~~earnings.py FMP calls bypass quota counter~~ FIXED
**File:** `swingdge-backend/app/services/earnings.py`
`_fetch_fmp()` now routes through `fmp_svc._get()` instead of making direct `httpx` calls.
FMP quota counter is now incremented for all earnings calendar lookups.

---

### [x] ~~trade_log.py crashes when position_size_shares is None~~ FIXED
**File:** `swingdge-backend/app/services/trade_log.py:49`
Added null guard: returns `None` early if `plan.position_size_shares is None` rather than
crashing with `TypeError: float() argument must be a string or a number, not 'NoneType'`.

---

### [x] ~~portfolio.py position limit hardcoded to 15% instead of reading trading rule~~ FIXED
**File:** `swingdge-backend/app/services/portfolio.py:290`
`POSITION_OVERWEIGHT` flag now compares against `await rules_svc.max_position_pct(db)`
(reads `max_position_pct` from `trading_rules` table) instead of hardcoded `15`.

---

### [x] ~~snaptrade.py sync never removes sold positions — stale DB rows persist forever~~ FIXED
**File:** `swingdge-backend/app/services/snaptrade.py`
After upserting live positions, `sync_portfolio` now deletes any holdings rows for each
synced account whose ticker is not in the live SnapTrade position set.
Return dict now includes `positions_deleted` count.
