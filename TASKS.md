# SwingEdge — Task List

> Reference architecture: `SwingEdge-Architecture-v3.md`
> Stack: FastAPI + Supabase + Vue 3 PWA + Render + Vercel + GitHub Actions + Telegram

---

## Phase 1 — Foundation

### Infrastructure Setup (do first — unblocks everything)
- [x] Create Supabase free project → copy `DATABASE_URL`
- [x] Sign up for Twelve Data API key (800 req/day free)
- [x] Sign up for Alpha Vantage API key (25 req/day free)
- [x] Sign up for Finnhub API key (60 req/min free)
- [x] Sign up for Financial Modeling Prep (FMP) API key (250 req/day free)
- [x] Sign up for Marketaux API key (100 req/day free)
- [x] Sign up for SnapTrade free tier → register app → get client ID + consumer key
- [ ] Connect Wealthsimple accounts to SnapTrade (Kripal TFSA + Sushma TFSA)
- [x] Create Telegram bot via @BotFather → save bot token + chat ID

### Backend — FastAPI Project
- [x] Initialize FastAPI project structure (`swingdge-backend/`)
- [x] Set up `pydantic-settings` config + `.env` file
- [x] Set up FastAPI middleware stack (CORS, rate limiting, request ID)
- [ ] Add HTTPS redirect middleware (currently not present — Render handles TLS termination at the edge, evaluate if still needed)
- [x] Implement JWT auth (single-user — login endpoint, token verification)
- [x] Build trigger endpoint skeleton with `TRIGGER_SECRET` auth (`POST /api/trigger/*`)
- [x] Deploy FastAPI to Render free tier (connect Git repo, add env vars)

### Database — Supabase
- [x] Write and run migrations for all core tables: ✓ ran via alembic
  - [x] `accounts`
  - [x] `holdings`
  - [x] `watchlist`
  - [x] `trade_plans`
  - [x] `trade_history`
  - [x] `market_snapshots`
  - [x] `sector_performance`
  - [x] `alerts`
  - [x] `api_cache`
  - [x] `trading_rules`
  - [x] `ticker_universe`
- [x] Seed default trading rules (1% risk, 2:1 R/R, 5-day earnings blackout, etc.)
- [x] Seed TSX + US ticker universe (50+ tickers)
- [x] Import Kripal's current 14 holdings (flag NKE -37%, UPS -22%, SOXL leveraged)

### Data Layer — Services
- [x] Implement Twelve Data client (batch quotes, indicators, caching)
- [x] Implement in-memory + PostgreSQL cache service (with TTL per data type)
- [x] Implement circuit breaker + Alpha Vantage fallback (`twelve_data.py` — 3-failure threshold, 5-min cooldown, AV fallback for quotes)
- [x] Implement SnapTrade client (sync positions + balances)
- [x] Build SnapTrade API endpoints (`app/api/snaptrade.py`):
  - [x] `POST /api/snaptrade/register` — register SnapTrade user
  - [x] `GET /api/snaptrade/connect` — get brokerage connection URL
  - [x] `GET /api/snaptrade/callback` — OAuth callback handler
  - [x] `GET /api/snaptrade/positions` — debug: list all account positions
  - [x] `GET /api/snaptrade/status` — connection status
- [x] Build portfolio API endpoints:
  - [x] `GET /api/portfolio/summary`
  - [x] `GET /api/portfolio/holdings`
  - [x] `GET /api/portfolio/accounts`
  - [x] `GET /api/portfolio/health` — open exposure, risk at stake, sector concentration
  - [x] `POST /api/portfolio/holdings` — manual holding upsert

### Frontend — Vue 3 PWA
- [x] Initialize Vue 3 + Vite PWA project (`swingdge-frontend/`)
- [x] Set up Vue Router, Pinia stores, Axios API client
- [ ] **Vercel deploy** (not set up yet — frontend has only run locally):
  - [x] Add `vercel.json` — SPA rewrite rule + build/output config (`swingdge-frontend/vercel.json`)
  - [x] Add `.github/workflows/frontend-deploy.yml` — builds on every push to `main` that touches `swingdge-frontend/`, Telegram alert on failure
  - [ ] Create Vercel project → connect `kripals/swing-edge` repo → set root directory to `swingdge-frontend/`
  - [ ] Set `VITE_API_URL` env var in Vercel dashboard to your Render backend URL (e.g. `https://swingdge-backend.onrender.com/api`)
  - [ ] Add `VITE_API_URL` as a GitHub Actions secret (used by the build workflow)
  - [ ] Verify production build passes in GHA and Vercel preview URL works
  - [ ] Confirm API calls reach Render backend (no CORS errors, no 401s)
- [x] Configure CORS — backend `allowed_origins` already includes `https://swingdge.vercel.app` (`config.py:50`)
- [x] Build Dashboard view (portfolio value, account breakdown, daily change)
- [x] Build Portfolio view (holdings by account, P&L, FX warning badges)

---

## Phase 2 — Analysis Engine ✓

### Backend
- [x] Implement technical indicator calculations (EMA 9/21, SMA 50/200, RSI, MACD, Bollinger Bands, ATR via Twelve Data; VWAP, volume ratio, relative strength computed locally)
- [x] Build trading rules engine (reads rules from `trading_rules` table, 5-min in-memory cache)
- [x] Build scanner engine with all filter criteria (uptrend, pullback, momentum, volume, ATR, market cap, earnings-safe, not overextended)
- [x] Build scanner signal scoring system (6 signal types, 9-component score, 0.4 threshold)
- [x] Build trade plan generator (entry zone, ATR stop, T1/T2 targets, position sizing)
- [x] Implement FX cost calculator (Wealthsimple 1.5% each way)
- [x] Implement earnings date checker + 5-day blackout enforcement (FMP → Finnhub fallback)
- [x] Build scanner API endpoints:
  - [x] `POST /api/scanner/run`
  - [x] `GET /api/scanner/results`
  - [x] `GET /api/scanner/history`
- [x] Build trade plan API endpoints:
  - [x] `GET /api/trades/plans`
  - [x] `POST /api/trades/plans`
  - [x] `GET /api/trades/plans/:id`
  - [x] `GET /api/trades/plans/generate/:ticker`
  - [x] `PATCH /api/trades/plans/:id/status`
  - [x] `PATCH /api/trades/plans/:id` (notes)
  - [x] `DELETE /api/trades/plans/:id` (soft delete)
  - [x] `GET /api/trades/history`
- [x] Build settings API endpoints:
  - [x] `GET /api/settings/rules`
  - [x] `PATCH /api/settings/rules/:key`

### Frontend
- [x] Build Scanner view (candidates list, signal type filter chips, history, run scan button)
- [x] Build Trade Plan detail view (SVG price ladder, violations, FX/earnings warnings, status controls)
- [x] Build Settings view (grouped editable rules, inline save, locked rules read-only)
- [x] Build Trade History view (win/loss stats strip, filter chips by status, trade rows with P&L)

---

## Phase 3 — Market Intelligence ✓

### Backend
- [x] Implement Bank of Canada Valet API (overnight rate, USD/CAD, CPI) → `services/boc.py`
- [x] Implement commodity price tracking (WTI oil, gold, natural gas, copper via Alpha Vantage)
- [x] Build sector rotation tracker (ETF performance: XEG, ZEB, XGD, ZRE, XIT, ZUT, XMA, XHC)
- [x] Build relative strength calculator (stock vs TSX Composite, 20-day) — already in `services/indicators.py`
- [x] Implement FMP + Finnhub fundamentals (P/E, EPS, earnings dates, analyst ratings) → `services/fmp.py`
- [x] Add macro context to trade plan generation (fundamentals panel on TradePlan view)
- [x] Build market data API endpoints (`app/api/market.py`):
  - [x] `GET /api/market/quote/:ticker`
  - [x] `GET /api/market/sectors`
  - [x] `GET /api/market/macro`
  - [x] `GET /api/market/earnings/:ticker`

### Frontend
- [x] Build Market view (macro snapshot + sector rotation + earnings countdown)
- [x] Build SectorHeatmap section (inline in Market.vue — color-coded tiles by % change, not a separate component file)
- [x] Build EarningsCountdown section (inline in Market.vue — days badge + blackout flag, not a separate component file)
- [x] Add macro context panel to Trade Plan detail view (P/E, EPS, beta, analyst consensus, EPS history)

---

## Phase 4 — Notifications & Scheduling ✓

### Notifications
- [x] Implement Telegram notification service (all alert types) → `services/telegram.py`
- [x] Implement alert fatigue prevention (cooldowns per alert type)
- [x] Implement PWA push notifications with VAPID keys (secondary channel) → `src/push.js` (stub — needs VAPID keys)
- [x] Build alert API endpoints:
  - [x] `GET /api/alerts`
  - [x] `POST /api/alerts/test`

### Scheduled Jobs (GitHub Actions)
- [x] Implement trigger endpoint handlers:
  - [x] `morning-scan` — full scanner pipeline at 9:45 AM ET
  - [x] `price-check` — check active trades vs entry/stop/target every 15 min
  - [x] `daily-summary` — Telegram daily summary at 4:45 PM ET
  - [x] `macro-update` — BoC + commodities at 6:00 PM ET
  - [x] `earnings-check` — flag holdings with earnings this week at 8:00 AM ET
  - [x] `portfolio-sync` — SnapTrade sync 2x daily
  - [x] `sector-update` — sector rotation at 4:30 PM ET
  - [x] `cache-cleanup` — purge expired cache rows
- [x] Create GitHub Actions workflow file (`.github/workflows/market-monitor.yml`)
- [x] Add Wake Render retry step (3 attempts, poll `/health`) to every GHA job — cold-start resilience
- [x] Add Telegram failure notification step to every GHA job — requires `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` GitHub secrets
- [ ] Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as GitHub Actions secrets
- [ ] Test full trigger flow: GitHub Actions → Render wake → scan → Telegram alert

### Frontend
- [x] Build Alerts view (`src/views/Alerts.vue`) — alert history, type filter chips, test button
- [x] Wire push notification registration in PWA (`push.js`)

---

## Phase 5 — Trade Tracking & Polish ✓

- [x] Build trade execution logging → `services/trade_log.py` (writes TradeHistory on stop/T2)
- [x] Build trade lifecycle (pending → active → hit_t1 → hit_t2/stopped) — price-check trigger + PATCH status endpoint
- [x] Build trade history view (win/loss stats, equity curve SVG) — TradeHistory.vue
- [x] Build portfolio health check (open exposure, risk at stake, max drawdown, sector concentration) → `GET /api/portfolio/health`
- [x] Build RiskGauge component (active trades bar, open exposure bar, risk at stake, win rate, max DD) — embedded in Dashboard
- [ ] Create materialized views for dashboard performance (deferred — not needed until scale)
- [x] Handle Render cold start gracefully in frontend (loading spinner + retry logic + cold-start banner) — Dashboard.vue
- [x] Responsive design pass (mobile-first nav, grid collapse, trade-prices hidden on mobile)
- [ ] End-to-end testing (key flows: scan → plan → alert → close)
- [ ] Final deploy verification: Vercel (frontend) + Render (backend) + Supabase (DB) + GitHub Actions (scheduler) all connected and talking to each other

---

## Phase 6 — Scanner Intelligence Upgrades

> Goal: improve signal quality by incorporating principles real traders use that the current scorer doesn't cover.

### 1. Sector Momentum Alignment
- [x] Map sector names to ETF tickers (`_SECTOR_ETF_MAP` constant in `scanner.py`)
- [x] Load sector ETF `change_pct` from in-memory cache (populated by `sector-update` trigger) at scan time
- [x] Award score component point if stock's sector ETF is positive on the day (`scanner.py` `_score()`)
- [x] Show sector ETF alignment badge on Scanner candidate card in frontend

### 2. 52-Week High Breakout Signal
- [x] Add `BREAKOUT_52W` signal type to `_detect_signals()`: price within 2% of 52-week high + volume ratio ≥ 1.5x
- [x] Compute 52-week high from 252-candle OHLCV window via `compute_52w_high()` in `indicators.py`
- [x] Add `above_52w_high` as scoring component in `_score()` (`scanner.py`)
- [x] Add `high_52w` field to `ScanCandidate`, `ScanResult` model + migration `0005`
- [x] Surface `52w_high` value on Scanner candidate card in frontend

### 3. ADX — Trend Strength
- [x] Add `adx_14` to Twelve Data indicators fetch in `twelve_data.py` (9th API call per ticker)
- [x] Add ADX ≥ 25 as scoring component in `scanner.py`
- [x] Add `adx_14` to `ScanCandidate`, `ScanResult` model + migration `0005`
- [x] Show ADX value on Scanner candidate card alongside RSI in frontend

### 4. News Sentiment (fill existing placeholder)
- [x] Implement Marketaux call in `services/news.py` — fetch last 3 articles per ticker, average sentiment score
- [x] Replace hardcoded `False` in scorer with live `sentiment_positive` result (`scanner.py`)
- [x] Cache results in `api_cache` table with 4-hour TTL to stay within 100 req/day limit
- [x] Show sentiment badge (positive/neutral/negative) on Scanner candidate card in frontend

### 5. Pivot Point Entry Refinement
- [x] Add `compute_pivot_points()` to `services/indicators.py` — classic P, S1, S2, R1, R2 from previous day OHLCV
- [x] In `trade_plan.py`, snap `entry_low` to nearest support pivot (S1 or S2) if within 1% of current price
- [x] Return `pivot_levels` dict in `TradePlanResult` and `TradePlanPreview` API response
- [x] Show pivot levels on Trade Plan price ladder SVG in frontend

### 6. Fix Signal Detection Accuracy (scanner logic bugs)
- [x] **RSI_REVERSAL**: Added `not above_sma_50` — now a distinct bottoming signal, no longer overlaps with RSI_PULLBACK. (`scanner.py:215`)
- [x] **EMA_CROSSOVER**: Now detects actual crossover using `ema_9_yesterday`/`ema_21_yesterday` computed from OHLCV candles in `indicators.py`. Falls back to ≤2% gap heuristic if candle history unavailable. (`scanner.py`, `indicators.py`)
- [x] **MACD_CROSSOVER**: Added minimum threshold `macd_hist > price * 0.005` (0.5% of price) — filters histogram noise. Same threshold in `_score()`. (`scanner.py:220`)
- [x] **Volume gate**: Moved `min_avg_vol` check outside `volume_ratio is not None` guard. (`scanner.py:154`)

### 7. Daily Portfolio Snapshot for True Daily P&L
- [x] Add a `portfolio-snapshot` trigger — writes today's total portfolio value + macro data to `market_snapshots` at 4:15 PM ET (`triggers.py`)
- [x] In `daily-summary` trigger, rename misleading `daily_change`/`daily_change_pct` → `total_pnl`/`total_pnl_pct` (`triggers.py`)
- [x] Update `fmt_daily_summary` in `telegram.py` — label changed from "Today" to "Unrealized P&L"
- [x] `daily-summary` now diffs today vs yesterday's snapshot for true daily P&L; falls back to unrealized P&L if no snapshot exists
- [x] Add `portfolio_value_cad` column to `market_snapshots` model + migration `0004`
- [x] Add `portfolio-snapshot` to GHA workflow (cron `15 20 * * 1-5`, `workflow_dispatch`)

---

## Phase 7 — Dynamic Ticker Universe

> Goal: replace the hardcoded 56-ticker watchlist with a live-synced universe so the scanner discovers new opportunities automatically. Two jobs: weekly universe sync (permanent additions) + daily momentum watchlist (temporary hot stocks).

### Schema

- [x] Alembic migration `0006` — add `expires_at` (DateTime, nullable) and `discovery_source` (String(30), nullable) to `ticker_universe`
- [x] Extend `cache-cleanup` trigger to deactivate expired dynamic tickers (`expires_at < now()` → `is_active=False`)

### Job 1: `ticker-discovery` (weekly — permanent additions)

- [x] Add `get_tsx_screener(_db, min_mktcap, min_volume, limit)` to `services/fmp.py` — calls FMP `/stock-screener` (1 FMP credit per run)
- [x] Filter screener results: exchange=TSX, market cap > $2B CAD, avg volume > 200k, not already in `ticker_universe`
- [x] Upsert new tickers into `ticker_universe` with `is_active=True`, `discovery_source="fmp_screener"`, no `expires_at`; deactivate delisted screener tickers
- [x] Build trigger endpoint handler `ticker-discovery` in `triggers.py` — Telegram summary of added/deactivated count
- [x] Add `ticker-discovery` to GitHub Actions workflow — weekly Sunday 6:00 AM ET (`0 10 * * 0`)
- [x] Add `ticker-discovery` to `workflow_dispatch` options in `market-monitor.yml`

### Job 2: `momentum-watchlist` (daily — temporary hot stocks)

- [x] Add `get_tsx_gainers(_db, min_volume, limit)` to `services/fmp.py` — calls FMP `/stock_market/gainers` (1 FMP credit per run)
- [x] Filter to TSX tickers (`.TO` suffix) NOT already in `ticker_universe`, volume > 500k
- [x] Upsert up to 10 new tickers per day with `is_active=True`, `discovery_source="momentum"`, `expires_at = now() + 7 days`
- [x] Build trigger endpoint handler `momentum-watchlist` in `triggers.py`
- [x] Add `momentum-watchlist` to GitHub Actions workflow — weekdays 10:30 AM ET (`30 14 * * 1-5`)
- [x] Add `momentum-watchlist` to `workflow_dispatch` options in `market-monitor.yml`

### Credit Budget Guard

- [x] Add `max_active_scan_tickers` rule to `trading_rules` table (default: 80) via `scripts/seed.py` + inserted into Supabase
- [x] In `scanner.py` `run_scan()`, cap list at `max_active_scan_tickers` — manual first, then fmp_screener, then momentum

### Testing & Validation

- [ ] Dry-run `ticker-discovery` via `workflow_dispatch` — confirm upsert, no duplicates, `:TSX` symbol format correct
- [ ] Dry-run `momentum-watchlist` via `workflow_dispatch` — confirm 7-day expiry, deactivation via cache-cleanup
- [ ] Run scanner against expanded universe — confirm no regressions in signal detection or scoring
- [ ] Confirm credit math stays under 800/day with 80-ticker cap: 80 × 9 = 720 credits

---

## Phase 8 — Portfolio Advisor

> Goal: daily hold/sell/watch recommendations for each holding based on live technicals and P&L. Separate from the swing scanner — this covers positions you already own.

### Backend

- [x] Create `services/advisor.py` — `AdvisorResult` dataclass + `analyze_holdings(db)` function
  - Load holdings from DB (reuse portfolio.py query pattern)
  - Fetch live quotes via `twelve_data.get_batch_quotes()`
  - Fetch indicators (RSI, SMA-50, EMA) via `twelve_data.get_indicators()`
  - Compute extras (volume ratio, relative strength) via `indicators.compute_extras()`
  - Check earnings proximity via `earnings.is_in_blackout()`
  - Skip leveraged ETFs from standard logic (flag SOXL and any 2x/3x ETFs separately — thresholds don't apply)
  - Apply FX-adjusted P&L for US-listed holdings (subtract 3% round-trip cost before threshold checks)
  - Apply decision logic per holding:
    - **SELL** — unrealized P&L ≤ −15% AND RSI < 45 AND below SMA-50 (trend broken)
    - **SELL** — unrealized P&L ≤ −8% AND price crossed below SMA-50 (breakdown)
    - **SELL** — unrealized P&L ≥ +25% AND RSI > 70 AND volume ratio dropping (extended)
    - **SELL** — earnings within 5 days (blackout — consider reducing)
    - **WATCH** — unrealized P&L −8% to −15%, still above SMA-50 (deteriorating)
    - **HOLD** — unrealized P&L ≥ +15%, RSI 50–70, momentum healthy (let it run)
    - **HOLD** — everything else (no action needed)
  - Return list of `AdvisorResult` (ticker, action, reason, key metrics, fx_adjusted_pnl_pct)

- [x] Add `GET /api/advisor/results` endpoint to a new `app/api/advisor.py` router
  - Calls `advisor.analyze_holdings(db)` and returns full results list
  - Used by frontend to display advisor panel
  - Register router in `main.py`

- [x] Add `portfolio-advisor` trigger endpoint to `triggers.py`
  - Calls `advisor.analyze_holdings(db)`
  - Sends Telegram message via `tg.fmt_portfolio_advice()`
  - Returns summary count of SELL / WATCH / HOLD
  - Add `portfolio-advisor` to the `workflow_dispatch` job options list in `market-monitor.yml`

- [x] Add `fmt_portfolio_advice(results)` formatter to `telegram.py`
  - Groups by action: SELL first, then WATCH, then HOLD
  - Shows ticker, FX-adjusted P&L%, action, and one-line reason per holding
  - Flags leveraged ETFs with a ⚠️ note
  - Adds cooldown: `portfolio_advice` type, 12h (once per half-day)

- [x] Add `portfolio-advisor` job to `.github/workflows/market-monitor.yml`
  - Runs daily at 4:02 PM ET (`2 20 * * 1-5`) before daily-summary at 4:45 PM (shifted 2 min to avoid cron collision with price-check)
  - Add to `workflow_dispatch` options list
  - Includes Wake Render retry step + Telegram failure notification (same pattern as other jobs)

### Frontend

- [x] Add Advisor panel to Portfolio view (`Portfolio.vue`)
  - Calls `GET /api/advisor/results` on page load
  - Shows each holding as a row: ticker | P&L% (FX-adjusted for US) | action chip (SELL=red, WATCH=amber, HOLD=green) | one-line reason
  - Flag leveraged ETFs with a ⚠️ badge instead of standard action chip
  - Collapse HOLD rows by default — expand on tap (keeps UI clean)
  - Show last-run timestamp at top of panel

### Testing & Validation

- [ ] Test `analyze_holdings()` against seeded holdings — confirm correct action assignment
- [ ] Confirm FX adjustment applies only to US-listed holdings (non-.TO tickers)
- [ ] Confirm SOXL and leveraged ETFs are excluded from standard thresholds
- [ ] Verify Telegram message formatting with mixed SELL/WATCH/HOLD portfolio
- [ ] Confirm cooldown prevents duplicate alerts within same day
- [ ] Dry-run `portfolio-advisor` via `workflow_dispatch` — confirm Telegram message received

---

## Phase 9 — SaaS Prep (Future / Optional)

- [ ] Upgrade Render → Railway Hobby ($5/mo) for always-on + APScheduler
- [ ] Multi-user auth (Supabase Auth or Clerk)
- [ ] Per-user trading rules
- [ ] Stripe billing integration
- [ ] Landing page + onboarding flow

---

## Notes

- **Hardcoded rules (never change without thought):** 1% risk/trade, 2:1 min R/R, 5-day earnings blackout, max 5 active trades, 10-day expiry, $2B min market cap, max 30% per sector, max 15% per position
- **FX cost:** US stocks without USD account = 3% round-trip (1.5% buy + 1.5% sell). Always show net gain after FX.
- **TSX tickers:** use `.TO` suffix with Twelve Data (e.g. `SU.TO`, `RY.TO`)
- **Render cold start:** ~30-60s. Frontend must handle gracefully with spinner + retry.
- **Supabase inactivity pause:** GitHub Actions daily triggers keep it active.
