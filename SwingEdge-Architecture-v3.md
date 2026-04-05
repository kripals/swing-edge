# SwingEdge — Complete Project Architecture (v3)

## Swing Trading Research, Portfolio Management & Alert System

**Owner:** Kripal Shrestha
**Location:** Ontario, Canada
**Broker:** Wealthsimple (2x TFSA accounts — Kripal + Sushma)
**Portfolio Sync:** SnapTrade API (free tier — 5 connections)
**Current Portfolio:** ~$7,287 CAD across TSX + US equities/ETFs
**Monthly Contribution:** $6,000–$8,000 CAD
**Goal:** Build a personal trading research app that scans markets, generates trade plans, tracks portfolio via live broker sync, and sends alerts — to grow portfolio through disciplined swing trading.

---

## TABLE OF CONTENTS

1. What Is This App?
2. Tech Stack (with explanations)
3. API Data Sources (detailed + rate limit budget)
4. Caching Strategy (no Redis — PostgreSQL + in-memory)
5. SnapTrade Integration (portfolio sync — corrected approach)
6. Wealthsimple-Specific Logic
7. Database Schema (with configurable trading rules)
8. Trading Rules Engine (database-driven)
9. Backend Architecture (modular monolith)
10. Security & Middleware Stack
11. Technical Analysis Engine (detailed)
12. Scanner System (detailed)
13. Trade Plan Generator (detailed)
14. Daily Data Pipeline
15. Frontend Architecture
16. Notification System (Telegram-primary)
17. Scheduled Jobs (GitHub Actions cron)
18. Current Holdings
19. Build Phases
20. Environment Variables
21. Glossary of Trading Terms

---

## 1. WHAT IS THIS APP?

SwingEdge is a personal swing trading research and portfolio management app. Here's what it does in plain English:

**Swing Trading** = buying a stock and holding it for a few days to a couple weeks, trying to catch a price "swing" up. You're not day-trading (buying and selling within minutes) and you're not investing for 10 years. You're looking for stocks that are about to move 5-15% over a few days, getting in, taking profit, and getting out.

**What SwingEdge does for you:**

1. **Scans the market** every morning before market open, looking at 50+ TSX and US stocks to find ones showing signals that a price swing is coming.

2. **Generates a trade plan** for each candidate: exactly where to buy, where to set your stop-loss (safety net), where to take profit, and how many shares to buy based on your account size and risk rules.

3. **Syncs with your actual Wealthsimple accounts** via SnapTrade so you always see your real holdings, real P&L, and real account balances — no manual entry.

4. **Monitors your active trades** throughout the day and alerts you via Telegram when a stock hits your entry zone, hits your profit target, or is approaching your stop-loss.

5. **Tracks your trading performance** over time — win rate, average gain, average loss, total P&L — so you can see if your strategy is working.

6. **Gives you macro context** — tracks Bank of Canada interest rates, oil/gold/commodity prices, USD/CAD exchange rate, and sector rotation so you understand WHY the market is moving.

---

## 2. TECH STACK

### Frontend: Vue 3 + Vite (PWA)

**What:** Vue.js is a JavaScript framework for building user interfaces. Vite is a fast build tool. PWA (Progressive Web App) means the website can be "installed" on your phone like an app.

**Why Vue:** You already know it. No learning curve.

**Why PWA:** 
- You can add it to your phone's home screen and it looks/feels like a native app
- PWA supports **push notifications** — so you get alerts on your phone without building a real iOS/Android app
- Free to deploy (no App Store fees, no Apple developer account)
- If you go SaaS later, users just visit a URL — no download needed

**Key packages:**
- `vue-router` — page navigation
- `pinia` — state management (like Vuex but simpler)
- `axios` — HTTP client for API calls
- `chart.js` or `lightweight-charts` — for price charts
- `vite-plugin-pwa` — PWA support

---

### Backend: Python 3.11+ with FastAPI

**What:** FastAPI is a modern Python web framework for building APIs. It's fast, has automatic documentation, and handles async operations well.

**Why Python over PHP:**
- Every financial/trading library is Python-native: `pandas` (data manipulation), `numpy` (math), `ta` or `pandas-ta` (technical indicators), `requests` (API calls)
- FastAPI auto-generates interactive API docs at `/docs` — your AI agent can test endpoints directly
- Async support means it can make multiple API calls simultaneously (important when fetching data for 50+ stocks)
- If you ever add ML-based predictions, Python is the only real choice

**Key packages:**
- `fastapi` — web framework
- `uvicorn` — ASGI server
- `sqlalchemy` — ORM for database
- `alembic` — database migrations
- `pandas` — data manipulation
- `pandas-ta` or `ta` — technical indicator calculations
- `httpx` — async HTTP client for API calls
- `python-telegram-bot` — Telegram notifications
- `pywebpush` — PWA push notifications (backup channel)
- `snaptrade-python-sdk` — SnapTrade integration
- `python-jose` — JWT authentication
- `bcrypt` — password hashing
- `cryptography` — AES-256 encryption for sensitive data (SnapTrade secrets)
- `pydantic-settings` — type-validated environment variable management
- `slowapi` — rate limiting

**NOTE:** No APScheduler in this stack. All scheduled jobs are handled by **GitHub Actions cron workflows** (see Task Scheduler section). This eliminates the need for an always-on server.

```bash
# Start command for Render
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

### Database: Supabase PostgreSQL (Free Tier — Always On)

**What:** Supabase provides a free managed PostgreSQL database that is always running — no sleeping, no cold starts.

**Why Supabase free tier:**
- 500 MB storage (more than enough — your 5-year dataset for 50 tickers is under 50 MB)
- Always-on — database never sleeps (unlike Render's free PostgreSQL which expires after 30 days)
- 2 free projects
- Built-in connection pooling via PgBouncer (important for Render's cold-start pattern)
- Good JSON support
- REST API included (optional — you'll use SQLAlchemy directly)
- Free daily backups
- Scales well if you go SaaS

**Supabase free tier limits:**
- 500 MB database storage
- 2 GB bandwidth
- 50,000 monthly active users (way more than you need)
- 1 GB file storage (not needed for this app)
- Paused after 1 week of inactivity (your GitHub Actions will keep it active)

**NOTE:** Supabase's free PostgreSQL does NOT include TimescaleDB extension. For this free-tier setup, we use standard PostgreSQL tables with proper indexing instead of hypertables. The performance difference at 50 tickers is zero — TimescaleDB matters at millions of rows, not thousands. If you upgrade to Railway later, you can add TimescaleDB then.

---

### Caching: NO Redis — PostgreSQL Cache Table + In-Memory

**What:** Instead of adding Redis as a separate service, we use two layers:
1. **Python dictionaries** (in-memory) for hot data during market hours — lost when Render sleeps, rebuilt on wake
2. **PostgreSQL regular table** for persistent cache that survives restarts and Render sleep cycles

**Why skip Redis:**
- At 50 tickers, standard PostgreSQL handles cache reads in under 5ms
- One fewer service to manage
- Redis would need its own hosting (another cost or free tier to manage)

**NOTE:** Supabase's managed PostgreSQL does not support UNLOGGED tables. We use a regular table instead — the performance difference is negligible at this scale.

```sql
-- Cache table for API responses
CREATE TABLE api_cache (
    cache_key VARCHAR(200) PRIMARY KEY,
    cache_value JSONB NOT NULL,
    provider VARCHAR(50),                -- "twelve_data", "finnhub", etc.
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_api_cache_expires ON api_cache (expires_at);
```

**Cache TTL Strategy:**

| Data Type | TTL During Market | TTL After Hours | Notes |
|-----------|-------------------|-----------------|-------|
| Daily OHLCV | 18-24 hours | Until next market open | Only changes once after close |
| Intraday quotes | 1-5 minutes | Until next market open | Hot data, keep in-memory |
| Technical indicators | 18-24 hours | Until next market open | Computed from daily OHLCV |
| Fundamentals (P/E, EPS) | 24-72 hours | 72 hours | Changes quarterly |
| Company profiles | 7-30 days | 30 days | Rarely changes |
| News & sentiment | 15-30 minutes | 1 hour | Stale quickly |
| Commodity prices | 5-15 minutes | Until next market open | Volatile during trading |
| BoC rate / macro | 24 hours | 24 hours | Changes on decision days only |
| Earnings dates | 24 hours | 24 hours | Changes infrequently |

---

### Task Scheduler: GitHub Actions Cron (FREE — replaces APScheduler)

**The problem:** Free hosting platforms (Render) sleep your app when idle. APScheduler only works inside a running process — if the server is asleep, no jobs fire and you miss trading alerts.

**The solution:** Move all scheduled tasks to **GitHub Actions cron workflows**. GitHub Actions runs on GitHub's servers for free (2,000 minutes/month on free plan). Each workflow wakes your Render backend by hitting a trigger endpoint, the backend does the work, sends Telegram alerts, then goes back to sleep.

**How it works:**

```
GitHub Actions (runs on schedule)
  → Makes HTTP request to your Render API: POST /api/trigger/morning-scan
  → Render wakes up from sleep (~30-60 second cold start)
  → FastAPI runs the scanner, calculates indicators, checks trades
  → Sends Telegram alerts if any signals fire
  → Render goes back to sleep after 15 min of inactivity
```

**Example GitHub Actions workflow:**

```yaml
# .github/workflows/market-monitor.yml
name: Market Monitor

on:
  schedule:
    # Morning scan — 9:45 AM ET (13:45 UTC during EDT, 14:45 UTC during EST)
    - cron: '45 13 * * 1-5'
    
    # Price check — every 15 min during market hours (9:30 AM - 4:00 PM ET)
    # These are approximate — GitHub Actions cron can be delayed up to 15 min
    - cron: '0,15,30,45 13-20 * * 1-5'
    
    # Daily summary — 4:45 PM ET
    - cron: '45 20 * * 1-5'
    
    # Macro update — 6:00 PM ET
    - cron: '0 22 * * 1-5'

  workflow_dispatch:  # Manual trigger button in GitHub UI

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Determine job type from schedule
        id: job_type
        run: |
          HOUR=$(date -u +%H)
          MIN=$(date -u +%M)
          if [ "$HOUR" -eq 13 ] && [ "$MIN" -eq 45 ]; then
            echo "type=morning-scan" >> $GITHUB_OUTPUT
          elif [ "$HOUR" -eq 20 ] && [ "$MIN" -eq 45 ]; then
            echo "type=daily-summary" >> $GITHUB_OUTPUT
          elif [ "$HOUR" -eq 22 ]; then
            echo "type=macro-update" >> $GITHUB_OUTPUT
          else
            echo "type=price-check" >> $GITHUB_OUTPUT
          fi

      - name: Trigger backend
        run: |
          curl -X POST \
            "${{ secrets.BACKEND_URL }}/api/trigger/${{ steps.job_type.outputs.type }}" \
            -H "Authorization: Bearer ${{ secrets.TRIGGER_SECRET }}" \
            -H "Content-Type: application/json" \
            --max-time 120 \
            --retry 3 \
            --retry-delay 10
```

**GitHub Actions free tier:**
- 2,000 minutes/month (runs on ubuntu-latest)
- Each trigger takes ~10-30 seconds (just an HTTP call + wait for response)
- Price check every 15 min × 6.5 hours × 22 trading days = ~572 runs/month
- At ~30 seconds each = ~286 minutes/month — well within the 2,000 limit

**The tradeoff — cold start delay:**
When Render has been sleeping and GitHub Actions triggers it, there's a **30-60 second cold start**. This means your price check alert might come 60 seconds later than it would on an always-on server. For a swing trader checking daily charts and holding for days, this is perfectly acceptable — you're not day-trading where seconds matter.

**⚠️ GitHub Actions cron timing caveat:**
GitHub Actions scheduled workflows can be delayed by up to 15-20 minutes during periods of high load on GitHub's servers. This is a known limitation. For a swing trader, a 15-minute delay on a morning scan is fine. But if this bothers you, upgrading to Railway Hobby ($5/month) with APScheduler gives you exact-second timing.

**Backend trigger endpoints:**
```
POST /api/trigger/morning-scan        # Run full scanner pipeline
POST /api/trigger/price-check         # Check prices vs trade plan levels
POST /api/trigger/daily-summary       # Send Telegram daily summary
POST /api/trigger/macro-update        # Update BoC rate, commodities, USD/CAD
POST /api/trigger/earnings-check      # Flag upcoming earnings
POST /api/trigger/portfolio-sync      # Sync via SnapTrade (2x daily)
POST /api/trigger/sector-update       # Update sector rotation
POST /api/trigger/cache-cleanup       # Clear expired cache
```

All trigger endpoints require a `TRIGGER_SECRET` in the Authorization header to prevent unauthorized access.

---

### Notifications: Telegram Bot (PRIMARY) + PWA Push (SECONDARY)

**Telegram Bot (PRIMARY — all alerts go here):**
- ~99%+ delivery reliability through native app infrastructure
- Sub-second latency
- Rich formatting (bold, links, emojis, inline keyboards)
- Supports images (for chart screenshots)
- Free, no limits
- Works on phone and desktop simultaneously
- Full message history preserved
- Setup takes 5 minutes via @BotFather

**PWA Push Notifications (SECONDARY — backup only):**
- ~80% delivery rate overall
- iOS is unreliable: requires PWA installed to Home Screen, iOS 16.4+, no background silent push
- Good for non-critical stuff (daily summary, scan complete)
- Use Web Push API with VAPID keys via `pywebpush` (free, simpler than Firebase)
- Set 5-minute TTL on push messages — stale trading alerts are worse than no alert

**Why Telegram is primary, not PWA push:** For a trading app where a missed stop-loss alert could cost you hundreds of dollars, you need the most reliable channel. Telegram delivers instantly on both Android and iOS without the platform-specific quirks of PWA push.

**Alert routing:**

| Priority | Channel | Examples |
|----------|---------|---------|
| CRITICAL | Telegram + PWA Push | Stop-loss hit, major rule violation |
| HIGH | Telegram + PWA Push | Entry signal triggered, target hit, stop approaching |
| MEDIUM | Telegram only | Earnings warning, FX warning, new scan candidate |
| LOW | Telegram only (batched) | Daily summary, weekly report, scan complete |

**Alert fatigue prevention:**
- No cooldown for CRITICAL alerts
- 1-minute cooldown between same-type HIGH alerts
- 5-minute cooldown for MEDIUM alerts
- Cap non-critical notifications at 3-5 per hour
- Use Telegram's message editing to UPDATE existing alerts rather than sending new ones

---

### Hosting (100% FREE)

| Component | Host | Cost | Always On? | Notes |
|-----------|------|------|-----------|-------|
| Frontend (Vue PWA) | **Vercel** | Free | Yes (static CDN) | 100GB bandwidth/month, global CDN, zero-config deploy from Git |
| Backend API (FastAPI) | **Render** | Free | No — sleeps after 15 min idle | Woken by GitHub Actions triggers. 750 hrs/month, ~30-60s cold start |
| Database (PostgreSQL) | **Supabase** | Free | Yes — always on | 500 MB storage, connection pooling, daily backups, never sleeps |
| Task Scheduler | **GitHub Actions** | Free | Runs on cron schedule | 2,000 min/month. Triggers Render endpoints on schedule |
| Notifications | **Telegram Bot** | Free | Yes | Instant delivery via @BotFather |

**Total cost: $0/month**

**How the pieces fit together:**
```
[GitHub Actions cron]
  → triggers every 15 min during market hours
  → POST /api/trigger/price-check
      ↓
[Render (FastAPI backend)]
  → wakes up in 30-60 seconds
  → connects to Supabase PostgreSQL (always available)
  → fetches market data from Twelve Data / Finnhub
  → runs scanner / checks trade levels
  → sends alerts via Telegram
  → goes back to sleep after 15 min idle
      ↓
[Supabase PostgreSQL]
  → always running, stores everything
  → positions, trade plans, rules, cache, history
      ↓
[Vercel (Vue PWA frontend)]
  → you open the app in browser / phone
  → calls Render API endpoints
  → Render wakes up, serves data, shows dashboard
```

**Render free tier details:**
- 750 hours/month of runtime (enough for ~31 days if running 24/7, but it sleeps when idle)
- 100 GB bandwidth
- Auto-deploy from Git
- Free SSL
- Sleeps after 15 minutes of no inbound requests — wakes on next request (30-60s cold start)
- **Important:** Render free tier web services spin down. Your scheduled jobs from GitHub Actions wake it up. When you open the frontend, the first API call also wakes it (you'll see a brief loading delay).

**Supabase free tier details:**
- 500 MB database storage
- Unlimited API requests
- 2 free projects
- Connection pooling via PgBouncer (6-mode connection pool)
- 50,000 monthly active users
- Paused after 1 week of inactivity — GitHub Actions keeps it active by triggering queries daily

**Upgrade path:** If cold starts become annoying or you want guaranteed timing, switch Render → Railway Hobby ($5/month). Code stays identical — just change the deploy target and add APScheduler back. The GitHub Actions workflows become optional backups.

---

## 3. API DATA SOURCES

### 3.1 Price & Technical Data (THE BACKBONE)

#### Twelve Data (PRIMARY)
- **Website:** twelvedata.com
- **Free tier:** 800 API credits/day, 8 credits/minute
- **Key feature: BATCH SUPPORT** — can fetch up to 120 symbols per HTTP request. Each symbol uses 1 credit but the batch only uses 1 of your 8/minute rate limit slots.
- **What it gives you:** Real-time and historical stock prices (OHLCV), pre-built technical indicators (RSI, MACD, EMA, SMA, Bollinger Bands, ATR, etc.), 20+ years of history
- **Exchanges:** TSX (use `TRP:TSX` or append `.TO`), NYSE, NASDAQ, and 50+ global exchanges
- **Why it's primary:** Best free tier. Batch support. One API call can return price + indicators.

#### Alpha Vantage (BACKUP + COMMODITIES)
- **Website:** alphavantage.co
- **Free tier:** 25 API calls/day (very limited)
- **What it gives you:** Stock prices AND commodity prices — commodities is where Alpha Vantage shines because Twelve Data doesn't have great commodity coverage on free tier.
- **Use for:** Oil (WTI), gold (XAU), natural gas, copper. Backup price data if Twelve Data is down.

#### Finnhub (SUPPLEMENT)
- **Website:** finnhub.io
- **Free tier:** 60 API calls/minute (86,400/day — very generous)
- **What it gives you:** Real-time quotes, company profiles, earnings calendar, company news, analyst recommendations
- **Use for:** Earnings dates (critical), real-time quote checks during market hours, company news

### 3.2 Daily API Budget (50+ tickers)

| API | Daily Limit | Planned Usage | Remaining Buffer |
|-----|------------|---------------|-----------------|
| **Twelve Data** | 800 credits | Pre-market batch (50) + 6 intraday refreshes of 20 hot tickers (120) + post-market (50) + misc (80) = ~300 | ~500 credits |
| **Finnhub** | 86,400/day (60/min) | Earnings (1) + company news (50) + spot quotes (100) = ~151 | Massive headroom |
| **FMP** | 250/day | Batch quotes (5) + fundamentals (20) + financials (10) + news (15) = ~50 | ~200 credits |
| **Marketaux** | 100/day | Top 20 TSX sentiment × 2 + alert-triggered (10) = ~50 | ~50 credits |
| **Alpha Vantage** | 25/day | Gold (2) + Oil (2) + Natural Gas (2) = 6 | ~19 credits |
| **Bank of Canada** | Unlimited | 3 calls/day | Unlimited |

**API Fallback Chain:**
When the primary API fails, the system automatically falls through:

```
1. Twelve Data (primary — batch, fast, good TSX)
   ↓ 3 failures in 5 min = mark unhealthy for 15 min
2. Finnhub (secondary — generous limits, good for US)
   ↓ 3 failures in 5 min = mark unhealthy for 15 min
3. FMP batch quotes (tertiary — 250/day, supports TSX)
   ↓ if all APIs fail
4. PostgreSQL cached data (last resort — show staleness warning in UI)
```

**Circuit breaker per provider:** After 3 failures within 5 minutes, mark provider as unhealthy for 15 minutes and fall to next. Track per-provider daily budgets, reset at midnight ET. Always update PostgreSQL cache on any successful fetch so the fallback layer stays fresh.

**For swing trading on daily timeframes, 15-minute delayed data is perfectly acceptable.** All free tiers provide this. Real-time execution pricing comes from your brokerage.

### 3.3 News & Sentiment

| API | Free Tier | Use For | Notes |
|-----|-----------|---------|-------|
| **Marketaux** | 100 req/day | TSX-specific news + sentiment scores (-1 to +1) | Best free source for TSX news |
| **Finnhub News** | Included in free tier | Company-specific news, press releases | Good for earnings/M&A alerts |
| **Alpha Vantage News** | Included in free key | AI sentiment scores, topic tags | Backup, shares 25/day limit |

**Usage rule:** News is for CONFIRMATION and AVOIDANCE only. Never enter a trade based on sentiment alone. Use it to: avoid earnings surprises, confirm momentum, and flag sector-wide events.

### 3.4 Canadian Macro Data — Bank of Canada (FREE, NO KEY)

#### Bank of Canada Valet API
- **Website:** bankofcanada.ca/valet
- **Cost:** Completely free, no signup, no API key needed

**What it gives you and why each matters:**

**BoC Policy Rate (overnight rate):**
- The interest rate the Bank of Canada sets. Affects everything.
- Rate UP → banks profit more (good for RY, TD, BNS), borrowing costs rise (bad for REITs, growth stocks)
- Rate DOWN → banks earn less on lending, borrowing cheaper (good for real estate, growth, REITs)
- Changes which sectors to trade.

**USD/CAD Exchange Rate:**
- Price of 1 USD in Canadian dollars.
- Directly affects your FX cost on US trades through Wealthsimple.
- Also affects Canadian exporters, oil prices (priced in USD), and your US holding values in CAD.

**CPI Inflation:**
- Consumer Price Index — how fast prices are rising.
- High inflation → BoC might raise rates → affects sector performance.
- BoC targets 2%. Significantly above or below triggers policy changes.

**Other available data:** Bond yields, CPI-trim, CPI-median, BCPI commodity index.

### 3.5 Commodities & Energy

**Why commodities matter for TSX:** TSX is ~18% energy and ~12% materials. When oil goes up, SU, CVE, CNQ go up almost in lockstep. Same with gold and ABX, AEM.

| Commodity | Source | What It Drives |
|-----------|--------|---------------|
| **WTI Crude Oil** | Alpha Vantage | SU.TO, CVE.TO, CNQ.TO, IMO.TO, MEG.TO — move almost 1:1 with oil |
| **Gold (XAU/USD)** | Alpha Vantage | ABX.TO, AEM.TO, K.TO, FNV.TO, WPM.TO — track gold price |
| **Natural Gas** | Alpha Vantage | Affects energy sector broadly |
| **Copper** | Alpha Vantage | TECK.TO, FM.TO, CUPR — also a leading economic indicator |

### 3.6 Company Fundamentals

#### Financial Modeling Prep (FMP)
- **Website:** financialmodelingprep.com
- **Free tier:** 250 requests/day
- **Supports TSX:** Yes
- **Provides:**
  - **P/E Ratio:** Price / Earnings per share. High (>30) = expects high growth or overvalued. Low (<10) = problems or undervalued.
  - **P/B Ratio:** Price / Book value. Below 1.0 = trading below asset value.
  - **EPS Growth:** Profit growth year-over-year. Positive = fundamental support for price increase.
  - **Debt-to-Equity:** Below 1.0 = healthy. Above 5.0 = danger zone.
  - **Revenue Trend:** Up or down quarter-over-quarter. Shrinking revenue = trap.

#### Finnhub Fundamentals
- **Included in free tier**
- **Provides:** Earnings dates, ESG scores, analyst ratings
- **Critical use: Earnings calendar** — NEVER enter a swing trade within 5 trading days of earnings. Stocks can gap 10-30% overnight after a report.

---

## 4. SNAPTRADE INTEGRATION (Portfolio Sync — Corrected Approach)

### What Is SnapTrade?

SnapTrade is a brokerage aggregation API. It connects to your Wealthsimple accounts and gives your app read access to your real portfolio — holdings, balances, positions, transactions.

### Free Tier Details

| Feature | Free Tier | Paid ($2/user/month) |
|---------|-----------|---------------------|
| Connections | 5 | Unlimited |
| API Requests | Unlimited | Unlimited |
| Real-time Data | Yes | Yes |
| Holdings & Balances | Yes | Yes |
| Transaction History | Yes | Yes |
| Trading | Yes (where supported) | Yes |

5 connections is perfect — you have 2 Wealthsimple accounts. A single connection covers all account types (TFSA, RRSP, FHSA) within one Wealthsimple login.

### CRITICAL: SnapTrade Sync Limitations

**SnapTrade syncs holdings automatically once per day.** You can trigger manual refresh via the `refreshBrokerageAuthorization` endpoint, but their docs recommend **no more than 4 Holdings API calls per day per user in background.**

**Wealthsimple provides 15-minute delayed quotes through SnapTrade** — unsuitable for price monitoring.

**The correct pattern:**

| Data | Source | Frequency |
|------|--------|-----------|
| What you OWN (tickers, shares, cost basis) | SnapTrade | 2x daily (startup + post-market) |
| Account balances and cash | SnapTrade | 2x daily |
| Transaction history | SnapTrade | 1x daily (post-market) |
| **Live prices and P&L** | **Twelve Data / Finnhub** | Every 15 min during market |

**Your app uses SnapTrade for POSITIONS ONLY and Twelve Data for PRICES.**

SnapTrade tells you: "You own 14.97 shares of VFV at an average cost of $150.57."
Twelve Data tells you: "VFV is currently trading at $162.32."
Your app calculates: "Unrealized P&L = (162.32 - 150.57) × 14.97 = +$175.87 (+7.8%)"

### Security

SnapTrade's `consumerKey` is highly sensitive — it generates HMAC-SHA256 signatures for every API request. The per-user `userSecret` returned during registration is also sensitive.

```
consumerKey → Store in Render environment variables (encrypted at rest)
userSecret  → Encrypt with AES-256 (Fernet) before storing in Supabase PostgreSQL
```

SnapTrade is SOC 2 Type II certified.

### Setup Flow

```
1. Create free account at dashboard.snaptrade.com
2. Generate free API key (clientId + consumerKey)
3. In your app's backend:
   a. Register a SnapTrade user (represents you)
   b. Generate a Connection Portal URL
   c. Open that URL in your browser
   d. Log in to Wealthsimple through the secure portal
   e. Authorize access
   f. Repeat for second Wealthsimple account
4. Your app can now pull real portfolio data
```

---

## 5. WEALTHSIMPLE-SPECIFIC LOGIC

### 5.1 FX Cost Engine

**The problem:** Wealthsimple charges 1.5% FX fee each direction. Round-trip on US stocks = 3%.

**Example:**
```
Buying AAPL at $200 USD, Target: $212 (+6%), Stop: $194 (-3%)

WITHOUT FX: Risk -3%, Reward +6%, R/R = 2:1 ← looks fine
WITH FX:    Risk -6% (3% loss + 3% FX), Reward +3% (6% - 3% FX), R/R = 0.5:1 ← TERRIBLE
```

Every US trade plan shows: raw gain, FX cost, net gain after FX, and warning if net gain is below threshold.

### 5.2 Account Awareness

| Account | Owner | Type | Tax | Use |
|---------|-------|------|-----|-----|
| TFSA #1 | Kripal | TFSA | 100% tax-free gains | Primary swing trading |
| TFSA #2 | Sushma | TFSA | 100% tax-free gains | Secondary / long-term |

TFSA is perfect for swing trading — all profits compound tax-free.

### 5.3 TSX Focus Universe (50+ Tickers)

Stored in the `ticker_universe` database table. Fully editable via Settings screen.

**Energy (10):** SU.TO, CNQ.TO, CVE.TO, ENB.TO, TRP.TO, PPL.TO, IMO.TO, MEG.TO, WCP.TO, ARX.TO

**Banks & Financials (11):** RY.TO, TD.TO, BNS.TO, BMO.TO, CM.TO, NA.TO, MFC.TO, SLF.TO, GWO.TO, POW.TO, IFC.TO

**Mining & Materials (9):** ABX.TO, AEM.TO, NTR.TO, FM.TO, TECK.TO, FNV.TO, WPM.TO, K.TO, LUN.TO

**Industrials & Transport (7):** CP.TO, CNR.TO, WFG.TO, TIH.TO, SJ.TO, CAE.TO, WSP.TO

**Tech & Telecom (6):** SHOP.TO, CSU.TO, OTEX.TO, T.TO, BCE.TO, RCI-B.TO

**Real Estate & Utilities (7):** BAM.TO, BN.TO, FTS.TO, EMA.TO, AQN.TO, REI-UN.TO, CAR-UN.TO

**ETFs for Sector Rotation (12):** XIU.TO, XIC.TO, XEI.TO, VFV.TO, VDY.TO, ZEB.TO, XEG.TO, XGD.TO, XMA.TO, ZSP.TO, XIT.TO, ZRE.TO

---

## 6. DATABASE SCHEMA

### 6.1 PostgreSQL Setup (Supabase)

```sql
-- Standard PostgreSQL on Supabase free tier
-- No TimescaleDB extension needed at this scale
```

### 6.2 Trading Rules (Database-Driven — NOT Hardcoded)

ALL trading rules live in the database. Change any rule from the Settings screen without touching code.

```sql
CREATE TABLE trading_rules (
    id SERIAL PRIMARY KEY,
    rule_key VARCHAR(100) UNIQUE NOT NULL,
    rule_value VARCHAR(500) NOT NULL,
    rule_type VARCHAR(20) NOT NULL,              -- "number", "boolean", "percentage", "json", "integer", "string"
    category VARCHAR(50) NOT NULL,               -- "risk", "scanner", "trading", "fx", "portfolio", "notification"
    display_name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    min_value VARCHAR(50),
    max_value VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by VARCHAR(100)
);
```

### 6.3 Default Trading Rules

```sql
-- ========== RISK MANAGEMENT ==========

INSERT INTO trading_rules VALUES
(DEFAULT, 'risk_per_trade_pct', '1.0', 'percentage', 'risk',
 'Risk Per Trade (%)',
 'Maximum percentage of account balance you can lose on a single trade. At 1% with $7,000 account, max loss per trade is $70. Controls position sizing. Professional traders use 0.5-2%. Never exceed 2% with a small account.',
 '0.25', '3.0', TRUE, NOW(), NULL),

(DEFAULT, 'min_risk_reward_ratio', '2.0', 'number', 'risk',
 'Minimum Risk/Reward Ratio',
 'Minimum ratio of potential profit to potential loss. At 2.0, target must be at least 2x your stop distance. With 2:1 R/R you only need to win 34% of trades to break even.',
 '1.5', '5.0', TRUE, NOW(), NULL),

(DEFAULT, 'max_active_trades', '5', 'integer', 'risk',
 'Maximum Active Trades',
 'Max simultaneous swing trades. With 5 trades at 1% risk each, max total risk is 5%. If all 5 hit stop (rare), you lose 5% — survivable.',
 '1', '10', TRUE, NOW(), NULL),

(DEFAULT, 'max_sector_exposure_pct', '30.0', 'percentage', 'risk',
 'Maximum Sector Exposure (%)',
 'Max portfolio percentage in any single sector. Prevents sector concentration risk — if oil crashes and 80% of your portfolio is energy, you get destroyed.',
 '15.0', '50.0', TRUE, NOW(), NULL),

(DEFAULT, 'max_single_position_pct', '15.0', 'percentage', 'risk',
 'Maximum Single Position (%)',
 'Max portfolio percentage for any single stock. ETFs are exempt (already diversified). Prevents a single stock collapse from destroying your portfolio.',
 '5.0', '25.0', TRUE, NOW(), NULL),

(DEFAULT, 'max_portfolio_risk_pct', '6.0', 'percentage', 'risk',
 'Maximum Total Portfolio Risk (%)',
 'Max combined risk across ALL open trades. Circuit breaker — if exceeded, no new trades until some close.',
 '3.0', '10.0', TRUE, NOW(), NULL),

-- ========== SCANNER ==========

(DEFAULT, 'scanner_min_market_cap', '2000000000', 'number', 'scanner',
 'Minimum Market Cap ($)',
 'Excludes penny stocks and micro-caps. Small stocks are manipulated easily, have wide spreads, and low liquidity.',
 '500000000', '50000000000', TRUE, NOW(), NULL),

(DEFAULT, 'scanner_sma_period', '50', 'integer', 'scanner',
 'Uptrend SMA Period',
 'Scanner requires price above this SMA. 50-day SMA is the standard medium-term trend indicator. Above = uptrend, below = downtrend.',
 '10', '200', TRUE, NOW(), NULL),

(DEFAULT, 'scanner_rsi_oversold', '30', 'integer', 'scanner',
 'RSI Oversold Level',
 'RSI below this = oversold (beaten down, might bounce). Scanner looks for RSI between this and upper bound, or crossing above this.',
 '15', '40', TRUE, NOW(), NULL),

(DEFAULT, 'scanner_rsi_upper_bound', '50', 'integer', 'scanner',
 'RSI Upper Bound',
 'Upper RSI limit for pullback filter. RSI 30-50 in uptrend = ideal entry — buying the dip in an uptrending stock.',
 '40', '60', TRUE, NOW(), NULL),

(DEFAULT, 'scanner_volume_multiplier', '1.5', 'number', 'scanner',
 'Volume Spike Multiplier',
 'Volume must be this many times above 20-day average. High volume confirms conviction. Low volume moves often reverse.',
 '1.0', '3.0', TRUE, NOW(), NULL),

(DEFAULT, 'scanner_min_price', '2.0', 'number', 'scanner',
 'Minimum Stock Price ($)',
 'Stocks under $2 are often penny stocks or companies in trouble. Wide spreads, low liquidity.',
 '1.0', '20.0', TRUE, NOW(), NULL),

(DEFAULT, 'scanner_min_avg_volume', '100000', 'integer', 'scanner',
 'Minimum Average Daily Volume',
 'Stocks trading fewer than 100K shares/day are illiquid — hard to sell when needed, spreads eat profits.',
 '10000', '1000000', TRUE, NOW(), NULL),

-- ========== TRADE EXECUTION ==========

(DEFAULT, 'trade_max_hold_days', '10', 'integer', 'trading',
 'Maximum Hold Period (trading days)',
 'Trades not resolved in this many days get flagged for review. Sideways trades tie up capital.',
 '5', '20', TRUE, NOW(), NULL),

(DEFAULT, 'trade_entry_buffer_pct', '1.0', 'percentage', 'trading',
 'Entry Buffer (%)',
 'How far above current price for entry zone top. At 1%, if price is $50, entry zone is $50-$50.50.',
 '0.5', '3.0', TRUE, NOW(), NULL),

(DEFAULT, 'trade_stop_atr_multiplier', '1.5', 'number', 'trading',
 'Stop-Loss ATR Multiplier',
 'Stop-loss distance in ATRs. At 1.5x, if stock moves $2/day avg, stop is $3 below entry. Gives room to breathe without getting stopped by daily noise.',
 '1.0', '3.0', TRUE, NOW(), NULL),

(DEFAULT, 'trade_target1_atr_multiplier', '3.0', 'number', 'trading',
 'Target 1 ATR Multiplier',
 'First profit target in ATRs. At 3.0x with 1.5x stop = 2:1 R/R. Take partial profit here.',
 '2.0', '5.0', TRUE, NOW(), NULL),

(DEFAULT, 'trade_target2_atr_multiplier', '4.5', 'number', 'trading',
 'Target 2 ATR Multiplier',
 'Second profit target in ATRs. At 4.5x with 1.5x stop = 3:1 R/R. Close remaining position.',
 '3.0', '8.0', TRUE, NOW(), NULL),

(DEFAULT, 'earnings_blackout_days', '5', 'integer', 'trading',
 'Earnings Blackout Period (trading days)',
 'No new trades within this many days of earnings. Stocks gap 10-30% on earnings — pure gamble.',
 '3', '15', TRUE, NOW(), NULL),

-- ========== FX / WEALTHSIMPLE ==========

(DEFAULT, 'fx_fee_per_conversion_pct', '1.5', 'percentage', 'fx',
 'Wealthsimple FX Fee Per Conversion (%)',
 'FX fee per conversion. Round-trip = 2x this. Update if WS changes fee or you switch brokers.',
 '0', '5.0', TRUE, NOW(), NULL),

(DEFAULT, 'has_usd_account', 'false', 'boolean', 'fx',
 'Has USD Account (Wealthsimple Plus)',
 'If true, FX cost = 0% for US trades. If false, 3% round-trip applied.',
 NULL, NULL, TRUE, NOW(), NULL),

(DEFAULT, 'fx_warning_threshold_pct', '3.0', 'percentage', 'fx',
 'FX Warning Threshold (%)',
 'Show FX WARNING if net gain after fees is below this. Helps avoid US trades where fees eat profit.',
 '1.0', '5.0', TRUE, NOW(), NULL),

(DEFAULT, 'us_trade_min_target_pct', '8.0', 'percentage', 'fx',
 'Minimum Target % for US Trades',
 'Minimum gross target for US stocks without USD account. Since FX costs 3%, a 5% target nets only 2%.',
 '5.0', '15.0', TRUE, NOW(), NULL),

-- ========== PORTFOLIO ==========

(DEFAULT, 'etf_exempt_from_position_limit', 'true', 'boolean', 'portfolio',
 'ETFs Exempt From Position Limit',
 'Broad ETFs (VFV, XIU) are already diversified. 33% in VFV ≠ 33% in one stock.',
 NULL, NULL, TRUE, NOW(), NULL),

(DEFAULT, 'portfolio_rebalance_alert_pct', '5.0', 'percentage', 'portfolio',
 'Rebalance Alert Threshold (%)',
 'Alert if any holding drifts more than this from target allocation. Set 0 to disable.',
 '0', '15.0', TRUE, NOW(), NULL),

-- ========== NOTIFICATION ==========

(DEFAULT, 'notify_stop_warning_pct', '1.5', 'percentage', 'notification',
 'Stop-Loss Warning Distance (%)',
 'Alert when price is within this % of stop-loss. Gives time to decide: hold or exit early.',
 '0.5', '5.0', TRUE, NOW(), NULL),

(DEFAULT, 'notify_daily_summary_time', '16:45', 'string', 'notification',
 'Daily Summary Time (ET)',
 'Time to send daily summary. 4:45 PM = 15 min after close, allows prices to settle.',
 NULL, NULL, TRUE, NOW(), NULL),

(DEFAULT, 'notify_morning_briefing_time', '09:15', 'string', 'notification',
 'Morning Briefing Time (ET)',
 'Time to send morning briefing. 9:15 AM = 15 min before open.',
 NULL, NULL, TRUE, NOW(), NULL);
```

### 6.4 Core Data Tables

```sql
-- ========== ACCOUNTS & PORTFOLIO ==========

CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    snaptrade_account_id VARCHAR(100) UNIQUE,
    snaptrade_connection_id VARCHAR(100),
    name VARCHAR(100) NOT NULL,
    institution VARCHAR(50) DEFAULT 'wealthsimple',
    account_type VARCHAR(20),
    account_number VARCHAR(50),
    currency VARCHAR(3) DEFAULT 'CAD',
    cash_balance DECIMAL(12,2) DEFAULT 0,
    total_value DECIMAL(12,2) DEFAULT 0,
    buying_power DECIMAL(12,2) DEFAULT 0,
    contribution_room DECIMAL(12,2),
    is_active BOOLEAN DEFAULT TRUE,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE holdings (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    snaptrade_position_id VARCHAR(100),
    ticker VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    name VARCHAR(200),
    shares DECIMAL(12,4) NOT NULL,
    avg_cost_per_share DECIMAL(10,4),
    current_price DECIMAL(10,4),
    market_value DECIMAL(12,2),
    book_value DECIMAL(12,2),
    unrealized_pnl DECIMAL(12,2),
    unrealized_pnl_pct DECIMAL(8,2),
    currency VARCHAR(3),
    sector VARCHAR(50),
    asset_type VARCHAR(20),
    is_us_stock BOOLEAN DEFAULT FALSE,
    portfolio_weight_pct DECIMAL(6,2),
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ========== TICKER UNIVERSE ==========

CREATE TABLE ticker_universe (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    exchange VARCHAR(10) NOT NULL,
    name VARCHAR(200),
    sector VARCHAR(50),
    industry VARCHAR(100),
    market_cap DECIMAL(15,2),
    currency VARCHAR(3),
    is_etf BOOLEAN DEFAULT FALSE,
    is_leveraged BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    added_at TIMESTAMP DEFAULT NOW()
);

-- ========== PRICE DATA (standard PostgreSQL table) ==========

CREATE TABLE daily_prices (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    ticker_id INTEGER NOT NULL REFERENCES ticker_universe(id),
    open DECIMAL(10,4),
    high DECIMAL(10,4),
    low DECIMAL(10,4),
    close DECIMAL(10,4),
    volume BIGINT,
    source VARCHAR(20)
);

CREATE INDEX idx_daily_prices_ticker_time ON daily_prices (ticker_id, time DESC);
CREATE UNIQUE INDEX idx_daily_prices_unique ON daily_prices (ticker_id, time);

-- ========== TECHNICAL INDICATORS (standard PostgreSQL table) ==========

-- Wide table — one column per indicator, avoids joins during scans
CREATE TABLE daily_indicators (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    ticker_id INTEGER NOT NULL REFERENCES ticker_universe(id),
    ema_9 DECIMAL(10,4),
    ema_21 DECIMAL(10,4),
    sma_50 DECIMAL(10,4),
    sma_200 DECIMAL(10,4),
    rsi_14 DECIMAL(6,2),
    macd_line DECIMAL(10,4),
    macd_signal DECIMAL(10,4),
    macd_histogram DECIMAL(10,4),
    bb_upper DECIMAL(10,4),
    bb_middle DECIMAL(10,4),
    bb_lower DECIMAL(10,4),
    atr_14 DECIMAL(10,4),
    vwap DECIMAL(10,4),
    volume_ratio DECIMAL(6,2),
    relative_strength DECIMAL(8,2)
);

CREATE INDEX idx_daily_ind_ticker_time ON daily_indicators (ticker_id, time DESC);
CREATE UNIQUE INDEX idx_daily_ind_unique ON daily_indicators (ticker_id, time);

-- Partial index for scan queries
CREATE INDEX idx_scan_rsi ON daily_indicators (time DESC, rsi_14) WHERE rsi_14 IS NOT NULL;

-- ========== SCANNER RESULTS ==========

CREATE TABLE scan_results (
    id SERIAL PRIMARY KEY,
    scan_date DATE NOT NULL,
    scan_time TIMESTAMP NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    exchange VARCHAR(10),
    current_price DECIMAL(10,4),
    signal_type VARCHAR(50) NOT NULL,
    signal_strength DECIMAL(4,2),
    rsi_14 DECIMAL(6,2),
    macd_histogram DECIMAL(10,4),
    volume_ratio DECIMAL(6,2),
    above_sma_50 BOOLEAN,
    atr_14 DECIMAL(10,4),
    relative_strength DECIMAL(8,2),
    sector VARCHAR(50),
    notes TEXT,
    has_trade_plan BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ========== TRADE PLANS ==========

CREATE TABLE trade_plans (
    id SERIAL PRIMARY KEY,
    scan_result_id INTEGER REFERENCES scan_results(id),
    ticker VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    sector VARCHAR(50),
    asset_type VARCHAR(20),
    price_at_generation DECIMAL(10,4),
    entry_low DECIMAL(10,4),
    entry_high DECIMAL(10,4),
    stop_loss DECIMAL(10,4),
    target_1 DECIMAL(10,4),
    target_2 DECIMAL(10,4),
    risk_per_share DECIMAL(10,4),
    reward_per_share_t1 DECIMAL(10,4),
    risk_reward_ratio_t1 DECIMAL(4,2),
    risk_reward_ratio_t2 DECIMAL(4,2),
    risk_amount DECIMAL(10,2),
    position_size_dollars DECIMAL(10,2),
    position_size_shares DECIMAL(10,4),
    fx_cost_round_trip_pct DECIMAL(4,2),
    gross_target_pct_t1 DECIMAL(6,2),
    net_target_pct_t1 DECIMAL(6,2),
    fx_warning BOOLEAN DEFAULT FALSE,
    pe_ratio DECIMAL(8,2),
    debt_to_equity DECIMAL(8,2),
    next_earnings_date DATE,
    earnings_days_away INTEGER,
    earnings_blackout BOOLEAN DEFAULT FALSE,
    oil_price DECIMAL(8,2),
    gold_price DECIMAL(10,2),
    usd_cad DECIMAL(8,4),
    boc_rate DECIMAL(4,2),
    rsi_14 DECIMAL(6,2),
    macd_histogram DECIMAL(10,4),
    sma_50 DECIMAL(10,4),
    atr_14 DECIMAL(10,4),
    volume_ratio DECIMAL(6,2),
    relative_strength_vs_index DECIMAL(8,2),
    signal_type VARCHAR(50),
    signal_description TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    account_id INTEGER REFERENCES accounts(id),
    actual_entry_price DECIMAL(10,4),
    actual_entry_date TIMESTAMP,
    actual_exit_price DECIMAL(10,4),
    actual_exit_date TIMESTAMP,
    actual_shares DECIMAL(10,4),
    actual_pnl DECIMAL(10,2),
    actual_pnl_pct DECIMAL(6,2),
    hold_days INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ========== TRADE HISTORY ==========

CREATE TABLE trade_history (
    id SERIAL PRIMARY KEY,
    trade_plan_id INTEGER REFERENCES trade_plans(id),
    account_id INTEGER REFERENCES accounts(id),
    ticker VARCHAR(20) NOT NULL,
    exchange VARCHAR(10),
    currency VARCHAR(3),
    sector VARCHAR(50),
    signal_type VARCHAR(50),
    entry_price DECIMAL(10,4),
    exit_price DECIMAL(10,4),
    shares DECIMAL(10,4),
    gross_pnl DECIMAL(10,2),
    fx_cost DECIMAL(10,2),
    net_pnl DECIMAL(10,2),
    net_pnl_pct DECIMAL(6,2),
    hold_days INTEGER,
    result VARCHAR(20),
    exit_reason VARCHAR(50),
    risk_reward_achieved DECIMAL(4,2),
    entered_at TIMESTAMP,
    exited_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ========== MARKET DATA ==========

CREATE TABLE market_snapshots (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    tsx_composite DECIMAL(10,2),
    tsx_composite_change_pct DECIMAL(6,2),
    sp500 DECIMAL(10,2),
    sp500_change_pct DECIMAL(6,2),
    usd_cad DECIMAL(8,4),
    boc_rate DECIMAL(4,2),
    wti_oil DECIMAL(8,2),
    gold DECIMAL(10,2),
    nat_gas DECIMAL(8,4),
    copper DECIMAL(8,4),
    cpi DECIMAL(4,2),
    vix DECIMAL(6,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sector_performance (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    sector VARCHAR(50) NOT NULL,
    etf_ticker VARCHAR(20),
    etf_price DECIMAL(10,2),
    performance_1d DECIMAL(6,2),
    performance_5d DECIMAL(6,2),
    performance_20d DECIMAL(6,2),
    relative_strength_vs_tsx DECIMAL(6,2),
    volume_ratio DECIMAL(6,2),
    money_flow VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(date, sector)
);

-- ========== ALERTS ==========

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    ticker VARCHAR(20),
    trade_plan_id INTEGER REFERENCES trade_plans(id),
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    sent_via VARCHAR(20),
    telegram_message_id VARCHAR(50),
    sent_at TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ========== API PROVIDER HEALTH (Circuit Breaker) ==========

CREATE TABLE api_provider_health (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) UNIQUE NOT NULL,
    is_healthy BOOLEAN DEFAULT TRUE,
    failure_count INTEGER DEFAULT 0,
    last_failure_at TIMESTAMP,
    unhealthy_until TIMESTAMP,
    daily_credits_used INTEGER DEFAULT 0,
    daily_credits_limit INTEGER,
    credits_reset_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO api_provider_health (provider, daily_credits_limit) VALUES
('twelve_data', 800),
('alpha_vantage', 25),
('finnhub', 86400),
('fmp', 250),
('marketaux', 100),
('bank_of_canada', NULL);

-- ========== CACHE (regular table — Supabase doesn't support UNLOGGED) ==========

CREATE TABLE api_cache (
    cache_key VARCHAR(200) PRIMARY KEY,
    cache_value JSONB NOT NULL,
    provider VARCHAR(50),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_api_cache_expires ON api_cache (expires_at);

-- ========== USER PREFERENCES ==========

CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    category VARCHAR(50),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ========== MATERIALIZED VIEW FOR SCANNER DASHBOARD ==========

CREATE MATERIALIZED VIEW scanner_dashboard AS
SELECT
    sr.*,
    tu.name as company_name,
    tu.sector,
    tu.market_cap
FROM scan_results sr
JOIN ticker_universe tu ON sr.ticker = tu.ticker
WHERE sr.scan_date = CURRENT_DATE
ORDER BY sr.signal_strength DESC;

CREATE UNIQUE INDEX idx_scanner_dashboard_id ON scanner_dashboard (id);
-- Refresh after each scan: REFRESH MATERIALIZED VIEW CONCURRENTLY scanner_dashboard;
```

---

## 7. TRADING RULES ENGINE

```python
class TradingRulesEngine:
    """
    All trading rules read from database. No parameters hardcoded.
    Rules cached in-memory, refreshed every 5 minutes or on-demand.
    """
    
    def get_rule(self, rule_key: str) -> any:
        """Get a rule value with type conversion."""
    
    def get_rules_by_category(self, category: str) -> dict:
        """Get all rules in a category."""
    
    def update_rule(self, rule_key: str, new_value: str, updated_by: str):
        """Update a rule, log change, refresh cache."""
    
    def validate_trade(self, trade_plan) -> list[str]:
        """
        Returns list of violations (empty = valid). Examples:
        - "R/R ratio 1.5 below minimum 2.0"
        - "Max active trades (5) reached"
        - "Earnings in 3 days (blackout is 5)"
        - "Sector exposure would exceed 30%"
        - "Net gain after FX only 2.1% (threshold: 3.0%)"
        """
```

---

## 8. BACKEND ARCHITECTURE (Modular Monolith)

**Why modular monolith, not microservices:** For a solo developer building a personal tool, a monolith maximizes development velocity. Amazon, Netflix, and Robinhood all started as monoliths. Organize by domain boundaries internally, deploy as a single FastAPI app. Extract services later if you go SaaS.

### 8.1 Project Structure

```
swingdge-backend/
├── app/
│   ├── main.py                          # FastAPI app, middleware stack, startup
│   ├── config.py                        # pydantic-settings env validation
│   ├── database.py                      # Supabase PostgreSQL connection
│   │
│   ├── models/                          # SQLAlchemy ORM models
│   │   ├── account.py
│   │   ├── holding.py
│   │   ├── trade_plan.py
│   │   ├── trade_history.py
│   │   ├── scan_result.py
│   │   ├── ticker_universe.py
│   │   ├── trading_rule.py
│   │   ├── market_snapshot.py
│   │   ├── sector_performance.py
│   │   ├── alert.py
│   │   ├── api_cache.py
│   │   └── api_provider_health.py
│   │
│   ├── schemas/                         # Pydantic request/response validation
│   │   ├── portfolio.py
│   │   ├── trade.py
│   │   ├── scanner.py
│   │   ├── market.py
│   │   └── settings.py
│   │
│   ├── api/                             # REST API routes
│   │   ├── portfolio.py
│   │   ├── scanner.py
│   │   ├── trades.py
│   │   ├── market.py
│   │   ├── alerts.py
│   │   ├── dashboard.py
│   │   ├── settings.py
│   │   └── auth.py                      # JWT authentication
│   │
│   ├── services/                        # Business logic
│   │   ├── snaptrade_service.py         # SnapTrade SDK — positions only, NOT prices
│   │   ├── data_fetcher.py              # Twelve Data + AV + Finnhub with circuit breaker
│   │   ├── cache_service.py             # In-memory + PostgreSQL cache table (NO Redis)
│   │   ├── circuit_breaker.py           # API provider health tracking
│   │   ├── technical_analysis.py        # Indicator calculations
│   │   ├── scanner_engine.py            # Market scanning
│   │   ├── trade_plan_generator.py      # Entry/stop/target/position size
│   │   ├── rules_engine.py              # Database-driven rules
│   │   ├── portfolio_tracker.py         # P&L using SnapTrade positions + Twelve Data prices
│   │   ├── fx_calculator.py             # Wealthsimple FX cost
│   │   ├── sector_rotation.py           # Sector strength tracking
│   │   ├── macro_tracker.py             # BoC + commodities
│   │   ├── earnings_checker.py          # Earnings dates + blackout
│   │   └── notification_service.py      # Telegram (primary) + Push (secondary)
│   │
│   ├── workers/                         # Triggered jobs (called by GitHub Actions)
│   │   ├── pipeline.py                  # Daily data pipeline orchestrator
│   │   ├── morning_scan.py
│   │   ├── price_monitor.py
│   │   ├── portfolio_sync.py            # SnapTrade sync (2x daily only)
│   │   ├── daily_summary.py
│   │   ├── morning_briefing.py
│   │   ├── macro_update.py
│   │   ├── sector_update.py
│   │   ├── earnings_check.py
│   │   └── cache_cleanup.py
│   │
│   ├── notifications/                   # Alert adapters
│   │   ├── telegram_adapter.py
│   │   └── push_adapter.py
│   │
│   └── utils/
│       ├── rate_limiter.py
│       ├── ticker_utils.py
│       ├── date_utils.py
│       └── formatters.py
│
├── alembic/
├── tests/
├── requirements.txt
├── alembic.ini
├── .env
├── .env.example
├── Dockerfile
├── Procfile                             # Render: web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
├── render.yaml                          # Render service config
└── docker-compose.yml
```

### 8.2 API Endpoints

```
# ========== AUTH ==========
POST   /api/auth/login                     # JWT login
POST   /api/auth/refresh                   # Refresh token

# ========== PORTFOLIO ==========
GET    /api/portfolio/summary
GET    /api/portfolio/accounts
GET    /api/portfolio/holdings
GET    /api/portfolio/holdings/:ticker
POST   /api/portfolio/sync                 # Manual SnapTrade sync
GET    /api/portfolio/health
GET    /api/portfolio/history

# ========== SCANNER ==========
POST   /api/scanner/run
GET    /api/scanner/results
GET    /api/scanner/results/:date
GET    /api/scanner/history

# ========== TRADE PLANS ==========
GET    /api/trades/plans
GET    /api/trades/plans/:id
POST   /api/trades/plans
POST   /api/trades/plans/generate/:ticker
PATCH  /api/trades/plans/:id/status
PATCH  /api/trades/plans/:id
DELETE /api/trades/plans/:id

# ========== TRADE HISTORY ==========
GET    /api/trades/history
GET    /api/trades/history/stats
GET    /api/trades/history/by-sector
GET    /api/trades/history/by-signal

# ========== MARKET ==========
GET    /api/market/quote/:ticker
GET    /api/market/chart/:ticker
GET    /api/market/macro
GET    /api/market/sectors
GET    /api/market/earnings/:ticker
GET    /api/market/news/:ticker

# ========== TICKER UNIVERSE ==========
GET    /api/universe
POST   /api/universe
PATCH  /api/universe/:ticker
DELETE /api/universe/:ticker

# ========== ALERTS ==========
GET    /api/alerts
GET    /api/alerts/unread
PATCH  /api/alerts/:id/acknowledge
POST   /api/alerts/test

# ========== SETTINGS ==========
GET    /api/settings/rules
GET    /api/settings/rules/:category
PATCH  /api/settings/rules/:key
GET    /api/settings/preferences
PATCH  /api/settings/preferences/:key

# ========== DASHBOARD ==========
GET    /api/dashboard

# ========== TRIGGER (called by GitHub Actions cron) ==========
POST   /api/trigger/morning-scan           # Run full scanner pipeline
POST   /api/trigger/price-check            # Check prices vs trade plan levels
POST   /api/trigger/daily-summary          # Send Telegram daily summary
POST   /api/trigger/macro-update           # Update BoC rate, commodities
POST   /api/trigger/earnings-check         # Flag upcoming earnings
POST   /api/trigger/portfolio-sync         # Sync via SnapTrade
POST   /api/trigger/sector-update          # Update sector rotation
POST   /api/trigger/cache-cleanup          # Clear expired cache
# All trigger endpoints require TRIGGER_SECRET in Authorization header
```

---

## 9. SECURITY & MIDDLEWARE STACK

### 9.1 Authentication

Start with **JWT using `python-jose`** and `bcrypt` password hashing. Single-user for now, but design with `user_id` foreign key on every table from day one for SaaS migration.

**SaaS migration path:** When ready, switch to Clerk (10,000 free MAUs, SOC 2 Type II) or Supabase Auth (50,000 free MAUs).

### 9.2 FastAPI Middleware Stack (ORDER MATTERS)

```python
# main.py — add middleware in this exact order

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware

app = FastAPI(
    title="SwingEdge API",
    docs_url="/docs" if settings.APP_ENV == "development" else None,  # Disable in prod
    redoc_url=None
)

# 1. CORS (MUST be first — if auth throws before CORS, browser sees CORS error)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-app.vercel.app",      # Production
        "http://localhost:5173",             # Local dev
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
    max_age=3600,                            # Cache preflight for 1 hour
)

# 2. Trusted Hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["your-app.onrender.com", "localhost"]
)

# 3. GZip (compress responses over 1KB)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 4. Rate limiting (slowapi)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Rate limits per endpoint type:
# Auth endpoints: 5/minute
# Trading endpoints: 30/minute  
# Market data reads: 60/minute
```

**CORS gotchas:**
- NEVER use `allow_origins=["*"]` with `allow_credentials=True` (browsers reject this)
- No trailing slashes in origin URLs
- Set `max_age=3600` to cache preflight responses

### 9.3 Sensitive Data Handling

```python
# Environment variables — use pydantic-settings
# Raises validation error at startup if any required secret is missing
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str                    # Supabase connection string
    SNAPTRADE_CLIENT_ID: str
    SNAPTRADE_CONSUMER_KEY: str          # Store in Render environment variables
    TWELVE_DATA_KEY: str
    TELEGRAM_BOT_TOKEN: str
    JWT_SECRET_KEY: str                  # Store in Render environment variables
    FERNET_ENCRYPTION_KEY: str           # For encrypting SnapTrade userSecret in DB
    TRIGGER_SECRET: str                  # Auth for GitHub Actions trigger endpoints
    
    class Config:
        env_file = ".env"

# SnapTrade userSecret — encrypt before storing
from cryptography.fernet import Fernet

def encrypt_secret(plaintext: str, key: str) -> str:
    f = Fernet(key.encode())
    return f.encrypt(plaintext.encode()).decode()

def decrypt_secret(ciphertext: str, key: str) -> str:
    f = Fernet(key.encode())
    return f.decrypt(ciphertext.encode()).decode()
```

---

## 10. DAILY DATA PIPELINE

The core engine runs this sequence each trading day:

```
Step 1: INGEST (~30 seconds)
  → Batch-fetch OHLCV from Twelve Data for all 50+ tickers
  → Bulk insert into daily_prices table
  → Update api_cache with fresh data

Step 2: COMPUTE (~5 seconds)
  → Calculate all technical indicators (RSI, SMA, MACD, BB, ATR, etc.)
  → Bulk insert into daily_indicators table

Step 3: SCAN (~2 seconds)
  → Run all scanner filters against latest indicators
  → Score each passing stock (signal strength 0-1)
  → Insert results into scan_results
  → Refresh materialized view: REFRESH MATERIALIZED VIEW CONCURRENTLY scanner_dashboard

Step 4: ALERT (~1 second)
  → Compare new scan results against active trade plans
  → Check entry/stop/target levels
  → Dispatch via Telegram (primary) + PWA push (secondary)

Step 5: SNAPSHOT (~1 second)
  → Calculate portfolio value and P&L
  → Insert into market_snapshots
  → Update sector_performance
```

---

## 11. TECHNICAL ANALYSIS ENGINE

### Indicators Calculated Per Ticker

**Moving Averages (Trend):**
- EMA 9 — very short-term trend
- EMA 21 — short-term trend. EMA 9 crossing above EMA 21 = bullish signal
- SMA 50 — medium-term trend. THE key filter: price above = uptrend
- SMA 200 — long-term trend

**RSI 14 (Momentum):** 0-100 scale. Above 70 = overbought. Below 30 = oversold. 30-50 in uptrend = pullback entry.

**MACD (12,26,9):** MACD line, signal line, histogram. Histogram turning positive = momentum shifting bullish.

**Bollinger Bands (20,2):** Price near lower band = potentially cheap. Above upper band = overextended.

**ATR 14 (Volatility):** Average daily range. Used for stop-loss and target distance.

**VWAP:** Volume-weighted fair price. Below VWAP = "cheap."

**Volume Ratio:** Today's volume / 20-day average. >1.5x = strong conviction.

**Relative Strength:** Performance vs TSX Composite over 20 days. Positive = outperforming.

---

## 12. SCANNER SYSTEM

### Signal Types

| Signal | Code | Meaning |
|--------|------|---------|
| RSI Pullback | `RSI_PULLBACK` | Uptrend + RSI pulled to 30-50. "Buy the dip." |
| RSI Reversal | `RSI_REVERSAL` | RSI crossed above 30. Momentum shifting bullish. |
| MACD Crossover | `MACD_CROSSOVER` | Histogram turned positive. |
| Volume Breakout | `VOLUME_BREAKOUT` | Broke resistance on >2x volume. |
| EMA Crossover | `EMA_CROSSOVER` | EMA 9 crossed above EMA 21. |
| Bollinger Bounce | `BB_BOUNCE` | Bouncing off lower Bollinger Band. |
| Combo | `COMBO` | Multiple signals at once. Strongest setups. |

### Signal Strength Score (0.0-1.0)

```
Components (each 0 or 1):
- Price > SMA 50
- Price > SMA 200
- RSI in buy zone (30-50)
- MACD histogram positive and increasing
- Volume > 1.5x average
- EMA 9 > EMA 21
- Price near lower Bollinger Band
- Relative strength > 0
- Positive news sentiment (if available)

Score = sum / total. ≥0.4 to pass scanner.
```

---

## 13. FRONTEND ARCHITECTURE (Vue 3 PWA)

### Key Screens

**Dashboard:** Total portfolio + daily change, account breakdown, active trade cards, sector heatmap, macro bar, alert feed.

**Scanner:** Run button / auto results, candidate cards with signal + R/R, filter chips (TSX/US/sector), tap to generate trade plan.

**Portfolio:** Tab per account, holdings with P&L, FX warning badges on US stocks, sector donut chart, health flags.

**Trade Plan Detail:** Chart with entry/stop/target lines, all fields, rule validations, macro context, fundamentals, action buttons.

**Market:** Sector rotation table, macro dashboard (BoC, oil, gold, USD/CAD charts), earnings calendar.

**Trade History:** Closed trades table, stats cards (win rate, avg win/loss, profit factor), equity curve.

**Settings:** Editable trading rules, SnapTrade status, notification config, ticker universe management.

---

## 14. SCHEDULED JOBS (GitHub Actions Cron)

All jobs run as GitHub Actions workflows that trigger Render API endpoints. Times shown in ET, converted to UTC in the cron expression.

| Job | Cron (UTC) | ET Time | Trigger Endpoint | Description |
|-----|-----------|---------|-----------------|-------------|
| `portfolio_sync` | `0 10,20 * * 1-5` | 6 AM + 4 PM | `/api/trigger/portfolio-sync` | SnapTrade sync (2x daily) |
| `earnings_check` | `0 12 * * 1-5` | 8 AM | `/api/trigger/earnings-check` | Flag upcoming earnings |
| `morning_briefing` | `15 13 * * 1-5` | 9:15 AM | `/api/trigger/morning-scan` | Scan + send briefing |
| `price_monitor` | `0,15,30,45 13-20 * * 1-5` | Every 15 min, 9-4 | `/api/trigger/price-check` | Check prices vs trade levels |
| `sector_update` | `30 20 * * 1-5` | 4:30 PM | `/api/trigger/sector-update` | Sector rotation |
| `daily_summary` | `45 20 * * 1-5` | 4:45 PM | `/api/trigger/daily-summary` | Telegram summary |
| `macro_update` | `0 22 * * 1-5` | 6 PM | `/api/trigger/macro-update` | BoC, commodities |
| `cache_cleanup` | `0 4 * * *` | 12 AM | `/api/trigger/cache-cleanup` | Clear expired cache |

**Monthly GitHub Actions usage estimate:**
- Price monitor: 26 runs/day × 22 days = 572 runs
- Other jobs: ~8 runs/day × 22 days = 176 runs
- Total: ~748 runs × ~30 sec each = ~374 minutes/month
- Free tier: 2,000 minutes/month — **well within budget**

**⚠️ Timing caveat:** GitHub Actions cron can be delayed 5-20 minutes during peak GitHub load. For swing trading on daily charts, this is acceptable. Your alerts might arrive a few minutes late, but you're not day-trading.

---

## 15. CURRENT HOLDINGS (Auto-Imported via SnapTrade)

| Ticker | Exchange | Shares | Value (CAD) | P&L % | Flags |
|--------|----------|--------|-------------|-------|-------|
| VFV | TSX | 14.97 | $2,431 | +7.79% | 33% of portfolio — core hold |
| XEI | TSX | 20.28 | $744 | +33.17% | Solid dividend ETF |
| ENB | TSX | 8.33 | $628 | +23.03% | Energy pipeline |
| NKE | US | 46.89 | $915 | ~-37% | ⚠️ Deep loss + FX drag |
| UPS | US | 3.25 | $444 | -21.83% | ⚠️ Downtrend + FX drag |
| VDY | TSX | 7.33 | $494 | +35.58% | Good dividend ETF |
| SOFI | US | 15 | $331 | -1.25% | US + FX cost |
| SPYM | US | 3.05 | $328 | +25.65% | Small, US |
| SOXL | US | 3.03 | $223 | +70.40% | ⚠️ 3x leveraged — risky to hold |
| ZEQT | TSX | 11.24 | $232 | +11.20% | All-equity ETF |
| HXT | TSX | 2 | $173 | +53.40% | S&P/TSX 60 ETF |
| CUPR | TSX | 300 | $171 | +18.75% | Copper momentum |
| QQC-F | TSX | 0.51 | $95 | +9.15% | Tiny NASDAQ position |
| VISA | US | 2.85 | $79 | +7.57% | Small + FX |

---

## 16. BUILD PHASES

### Phase 1: Foundation (Week 1-2)
- [ ] Create Supabase free project + get connection string
- [ ] Initialize FastAPI with pydantic-settings, security middleware stack
- [ ] Deploy FastAPI to Render free tier (connect Git repo)
- [ ] Run database migrations on Supabase (all tables + indexes)
- [ ] Insert default trading rules + ticker universe
- [ ] Sign up for all API keys (Twelve Data, Alpha Vantage, Finnhub, FMP, Marketaux)
- [ ] Sign up for SnapTrade free tier + connect Wealthsimple accounts
- [ ] Implement JWT auth (single user)
- [ ] Implement SnapTrade connection + portfolio sync (positions only)
- [ ] Implement Twelve Data client with circuit breaker + caching
- [ ] Build portfolio API endpoints (prices from Twelve Data, positions from SnapTrade)
- [ ] Build trigger endpoints with TRIGGER_SECRET authentication
- [ ] Initialize Vue 3 + Vite PWA on Vercel
- [ ] Build Dashboard + Portfolio views with real data
- [ ] Configure CORS between Vercel and Render

### Phase 2: Analysis Engine (Week 3-4)
- [ ] Implement technical indicator calculations
- [ ] Build scanner engine with filters + signal scoring
- [ ] Build trade plan generator with position sizing + FX cost
- [ ] Implement earnings blackout enforcement
- [ ] Build trading rules engine (reads from database)
- [ ] Build API cache service (in-memory + PostgreSQL cache table)
- [ ] Build API fallback chain with circuit breakers
- [ ] Build Scanner + Trade Plan views in frontend
- [ ] Build Settings view (editable rules)

### Phase 3: Market Intelligence (Week 5-6)
- [ ] Implement BoC Valet API + commodity tracking
- [ ] Build sector rotation tracker
- [ ] Build relative strength calculator
- [ ] Build Market view (macro + sectors)
- [ ] Build sector heatmap component
- [ ] Implement FMP + Finnhub fundamentals
- [ ] Add macro context to trade plans

### Phase 4: Notifications & Scheduling (Week 7-8)
- [ ] Set up Telegram bot via @BotFather
- [ ] Implement notification service (Telegram primary + Push secondary)
- [ ] Implement alert fatigue prevention (cooldowns, caps)
- [ ] Create GitHub Actions cron workflows (market-monitor.yml)
- [ ] Build all trigger endpoint handlers (morning-scan, price-check, etc.)
- [ ] Build daily data pipeline orchestrator
- [ ] Test full trigger flow: GitHub Actions → Render wake → scan → Telegram alert
- [ ] Implement PWA push with VAPID keys (secondary channel)
- [ ] Build alert feed in frontend

### Phase 5: Trade Tracking & Polish (Week 9-10)
- [ ] Build trade execution logging + lifecycle
- [ ] Build trade history with stats + equity curve
- [ ] Build portfolio health check
- [ ] Build materialized views for dashboard performance
- [ ] Responsive design, loading states, error handling
- [ ] Handle Render cold start gracefully in frontend (loading spinner, retry logic)
- [ ] End-to-end testing
- [ ] Final deploy: Vercel (frontend) + Render (backend) + Supabase (DB) + GitHub Actions (cron)

### Phase 6: SaaS Prep (Future)
- [ ] Upgrade to Railway Hobby ($5/month) for always-on + APScheduler (optional)
- [ ] Multi-user auth (Clerk or Supabase Auth)
- [ ] Per-user trading rules
- [ ] Stripe billing
- [ ] Landing page + onboarding

---

## 17. ENVIRONMENT VARIABLES

### Render Environment Variables (set in Render dashboard)

```env
# ========== DATABASE (Supabase) ==========
DATABASE_URL=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres

# ========== SNAPTRADE ==========
SNAPTRADE_CLIENT_ID=your_client_id
SNAPTRADE_CONSUMER_KEY=your_consumer_key
SNAPTRADE_USER_ID=your_registered_user_id
SNAPTRADE_USER_SECRET_ENCRYPTED=encrypted_value    # AES-256 encrypted

# ========== MARKET DATA APIs ==========
TWELVE_DATA_KEY=your_key
ALPHA_VANTAGE_KEY=your_key
FINNHUB_KEY=your_key
FMP_KEY=your_key
MARKETAUX_KEY=your_key

# ========== TELEGRAM ==========
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# ========== SECURITY ==========
JWT_SECRET_KEY=random_secret
FERNET_ENCRYPTION_KEY=your_fernet_key
TRIGGER_SECRET=random_secret_for_github_actions    # Auth for trigger endpoints

# ========== PWA PUSH ==========
VAPID_PUBLIC_KEY=your_public_key
VAPID_PRIVATE_KEY=your_private_key
VAPID_CLAIM_EMAIL=your@email.com

# ========== APP CONFIG ==========
APP_ENV=development
TIMEZONE=America/Toronto
LOG_LEVEL=INFO
```

### GitHub Actions Secrets (set in GitHub repo → Settings → Secrets)

```
BACKEND_URL=https://your-app.onrender.com
TRIGGER_SECRET=same_secret_as_render
```
```

---

## 18. GLOSSARY OF TRADING TERMS

| Term | Meaning |
|------|---------|
| **Swing Trade** | Holding a stock for days-weeks to profit from a price swing |
| **Entry Zone** | Price range where you plan to buy |
| **Stop-Loss** | Price where you sell to limit losses |
| **Target** | Price where you sell for profit |
| **Risk/Reward** | Ratio of potential profit to potential loss |
| **Position Size** | How many shares/dollars in a trade |
| **ATR** | Average True Range — daily movement measure |
| **RSI** | Relative Strength Index — momentum (0-100) |
| **MACD** | Moving Average Convergence Divergence — trend/momentum |
| **EMA/SMA** | Exponential/Simple Moving Average — trend following |
| **Bollinger Bands** | Volatility bands around a moving average |
| **VWAP** | Volume Weighted Average Price — fair value |
| **Overbought** | RSI >70 — may pull back |
| **Oversold** | RSI <30 — may bounce |
| **Pullback** | Temporary dip in an uptrend |
| **Breakout** | Price moving above resistance with volume |
| **Sector Rotation** | Money flowing between sectors |
| **Relative Strength** | Performance vs benchmark index |
| **FX Cost** | Wealthsimple's currency conversion fee |
| **TFSA** | Tax-Free Savings Account — gains not taxed |
| **Market Cap** | Company total value (price × shares) |
| **P/E Ratio** | Price / Earnings per share |
| **Profit Factor** | Total gains / Total losses |
| **Drawdown** | Peak-to-trough portfolio decline |
| **Equity Curve** | Cumulative P&L chart over time |
| **Circuit Breaker** | Auto-disables an API provider after repeated failures |
| **Cold Start** | Delay when Render wakes your sleeping backend (~30-60 seconds) |
| **Materialized View** | Pre-computed query result stored as a table — fast reads |
| **Modular Monolith** | Single deployable app organized by domain boundaries internally |
| **GitHub Actions Cron** | Free scheduled workflows that trigger your backend endpoints |
| **Trigger Endpoint** | API endpoint that runs a job when called by GitHub Actions |

---

*⚠️ Disclaimer: SwingEdge is a research and tracking tool. It does not constitute financial advice. Always apply your own risk management and judgment before placing trades. Past performance does not guarantee future results.*
