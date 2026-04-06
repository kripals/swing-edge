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
- [x] Set up FastAPI middleware stack (CORS, rate limiting, HTTPS redirect, request ID)
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
- [ ] Implement circuit breaker + Alpha Vantage fallback
- [x] Implement SnapTrade client (sync positions + balances)
- [x] Build portfolio API endpoints:
  - [x] `GET /api/portfolio/summary`
  - [x] `GET /api/portfolio/holdings`
  - [x] `GET /api/portfolio/accounts`

### Frontend — Vue 3 PWA
- [x] Initialize Vue 3 + Vite PWA project (`swingdge-frontend/`)
- [x] Set up Vue Router, Pinia stores, Axios API client
- [ ] Configure Vercel deploy (connect Git repo)
- [x] Configure CORS between Vercel frontend and Render backend
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
- [x] Build SectorHeatmap component (inline in Market view — color-coded tiles by % change)
- [x] Build EarningsCountdown component (inline in Market view — days badge + blackout flag)
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
- [ ] Final deploy verification: Vercel + Render + Supabase + GitHub Actions all connected

---

## Phase 6 — SaaS Prep (Future / Optional)

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
