# SwingEdge — Complete Project Architecture (v2)

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
3. API Data Sources (detailed)
4. SnapTrade Integration (portfolio sync)
5. Wealthsimple-Specific Logic
6. Database Schema (with configurable trading rules)
7. Trading Rules Engine (database-driven)
8. Backend Architecture
9. Technical Analysis Engine (detailed)
10. Scanner System (detailed)
11. Trade Plan Generator (detailed)
12. Frontend Architecture
13. Notification System
14. Scheduled Jobs
15. Current Holdings
16. Build Phases
17. Environment Variables
18. Glossary of Trading Terms

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
- `uvicorn` — ASGI server to run FastAPI
- `sqlalchemy` — ORM for database
- `alembic` — database migrations
- `pandas` — data manipulation
- `pandas-ta` or `ta` — technical indicator calculations
- `httpx` — async HTTP client for API calls
- `apscheduler` — scheduled tasks (cron jobs)
- `python-telegram-bot` — Telegram notifications
- `pywebpush` — PWA push notifications
- `redis` (optional) — caching API responses
- `snaptrade-python-sdk` — SnapTrade integration

---

### Database: PostgreSQL

**What:** A relational database. Stores all your data in structured tables.

**Why PostgreSQL:**
- Free and open source
- Handles time-series data well (important for price history, trade history)
- Good JSON support if you need flexible fields
- Every hosting platform supports it
- Scales well if you go SaaS

---

### Cache: Redis (optional, can use in-memory for MVP)

**What:** An in-memory key-value store. Think of it as a super-fast temporary storage.

**Why:** You're limited to 800 API calls/day on Twelve Data. If you fetch AAPL's price once, cache it for 15 minutes so you don't waste another call if you need it again. Without caching, you'll burn through your free tier in an hour.

**MVP alternative:** Use a simple Python dictionary with TTL (time-to-live) expiry. Upgrade to Redis when needed.

---

### Task Scheduler: APScheduler

**What:** A Python library that runs functions on a schedule — like cron jobs but inside your Python app.

**Why:** You need things to happen automatically:
- Run the scanner every morning at 9:45 AM ET
- Check prices every 15 minutes during market hours
- Send daily summary at 4:45 PM ET
- Update macro data once per day

APScheduler lets you define all of these inside your FastAPI app without needing a separate cron service.

---

### Notifications: Telegram Bot + PWA Push

**Telegram Bot:**
- Free, instant delivery
- Rich formatting (bold, links, emojis)
- Can include buttons (e.g., "View Trade Plan" link)
- Works on phone and desktop
- Setup takes 5 minutes via @BotFather
- Perfect for urgent alerts (entry signals, stop-loss warnings)

**PWA Push Notifications:**
- Browser/phone notifications even when app is closed
- Good for less urgent stuff (daily summary, scan complete)
- Requires VAPID keys (free to generate)
- Uses the Web Push API standard

**Why not Discord:** Discord is built for communities. For a personal tool, Telegram is cleaner — it's just you and the bot in a private chat.

**Why not SMS:** Costs money per message. Telegram is free with no limits.

**Why not Email:** Too slow, gets buried in inbox. Trading alerts need to be instant.

---

### Hosting

| Component | Host | Free Tier | Notes |
|-----------|------|-----------|-------|
| Frontend (Vue PWA) | **Vercel** | 100GB bandwidth/month | Zero config deploy from Git |
| Backend (FastAPI) | **Railway** | $5 free credit/month | Backend + Postgres + cron |
| Backend (Alternative) | **Render** | 750 hrs/month | Spins down after 15 min inactivity (slow cold start) |
| Database | **Railway Postgres** | Included in Railway | Or Supabase free tier (500MB) |
| Redis (if needed) | **Upstash** | 10,000 commands/day | Free tier, serverless Redis |

**Cost: $0/month** for personal use. Railway's $5 credit covers a small backend + database easily.

---

## 3. API DATA SOURCES

### 3.1 Price & Technical Data

This is the backbone of everything. Without accurate price data, nothing else works.

#### Twelve Data (PRIMARY)
- **Website:** twelvedata.com
- **Free tier:** 800 API credits/day, 8 credits/minute
- **What it gives you:** Real-time and historical stock prices (open, high, low, close, volume), pre-built technical indicators (RSI, MACD, EMA, SMA, Bollinger Bands, ATR, etc.), 20+ years of history
- **Exchanges:** TSX (append `.TO` to tickers, e.g., `CNQ.TO`), NYSE, NASDAQ, and 50+ global exchanges
- **Why it's primary:** Best free tier by far. One API call can return price + multiple indicators. Their technical indicator endpoints mean you don't have to calculate RSI/MACD yourself — though we will calculate locally too for reliability.
- **Rate limit strategy:** 800/day means ~16 stocks × 50 calls each. Cache aggressively. Historical daily candles don't change after market close, so fetch once and store.

#### Alpha Vantage (BACKUP + COMMODITIES)
- **Website:** alphavantage.co
- **Free tier:** 25 API calls/day (very limited)
- **What it gives you:** Stock prices, technical indicators, AND commodity prices (WTI crude oil, natural gas, gold, copper) — commodities is where Alpha Vantage shines because Twelve Data doesn't have great commodity coverage on free tier.
- **Use for:** Oil (WTI), gold (XAU), natural gas, copper. Also backup if Twelve Data is down.
- **Key endpoints:**
  - `function=WTI` — crude oil price
  - `function=NATURAL_GAS` — natural gas price  
  - `function=CURRENCY_EXCHANGE_RATE&from_currency=XAU&to_currency=USD` — gold price

#### Finnhub (SUPPLEMENT)
- **Website:** finnhub.io
- **Free tier:** 60 API calls/minute (very generous rate limit)
- **What it gives you:** Real-time quotes, company profiles, earnings calendar, company news, analyst recommendations, financials
- **Use for:** Earnings dates (critical — we need to know when a company reports earnings to avoid holding through it), real-time quote checks during market hours, company news for confirmation
- **Why it's great:** The rate limit is per-minute not per-day, so you can make 60 calls/minute which is plenty for real-time monitoring

### 3.2 News & Sentiment

Sentiment analysis gives you a "mood score" for a stock based on recent news. A score of -1 means very negative news, 0 is neutral, +1 is very positive.

#### Marketaux (TSX-FOCUSED NEWS)
- **Website:** marketaux.com
- **Free tier:** 100 requests/day
- **What it gives you:** News articles tagged by ticker symbol, with AI-generated sentiment scores. Each article gets a score from -1 to +1 and is tagged to specific stock tickers.
- **Why it matters:** This is the best free source for **TSX-specific** news. Most news APIs are US-focused; Marketaux actually tags TSX stocks reliably.
- **Use case:** Before entering a trade, check if there's overwhelmingly negative news. If sentiment score is below -0.5, flag the trade for review.

#### Alpha Vantage News Sentiment
- **Included in free key** (shares the 25/day limit)
- **What it gives you:** News articles with AI sentiment scores, topic tags, relevance scores per ticker
- **Use case:** Backup news source, especially for US stocks

#### Finnhub News
- **Included in free tier**
- **What it gives you:** Company-specific news, market-wide news, press releases
- **Use case:** Check for earnings announcements, M&A activity, regulatory changes before entering a trade

### 3.3 Canadian Macro Data — Bank of Canada (FREE, NO KEY)

**What is macro data?** = The big-picture economic numbers that affect the entire market, not just one stock.

#### Bank of Canada Valet API
- **Website:** bankofcanada.ca/valet
- **Cost:** Completely free, no signup, no API key needed
- **What it gives you:**

  **BoC Policy Rate (overnight rate):**
  - This is the interest rate the Bank of Canada sets. It affects everything.
  - When rates go UP: banks make more money (good for RY, TD, BNS), but borrowing costs rise (bad for REITs, real estate, growth stocks). Bond prices fall.
  - When rates go DOWN: banks make less on lending, but borrowing becomes cheaper (good for real estate, growth stocks, REITs).
  - Why you care: If BoC cuts rates, bank stocks might dip but REITs rally. If BoC hikes, opposite. This changes which sectors to trade.

  **USD/CAD Exchange Rate:**
  - The price of 1 USD in Canadian dollars.
  - Why you care: This directly affects your FX cost on US trades through Wealthsimple. If USD/CAD is 1.36, then $1 USD costs $1.36 CAD. Wealthsimple charges 1.5% ON TOP of this conversion.
  - Also affects: Canadian exporters (strong USD = good for Canadian companies selling to US), oil prices (oil is priced in USD), and your portfolio value (US holdings are worth more in CAD when USD is strong).

  **CPI Inflation:**
  - Consumer Price Index — measures how fast prices are rising.
  - Why you care: High inflation → BoC might raise rates → affects which sectors perform. Low inflation → rates might come down → different trade opportunities.
  - BoC targets 2% inflation. Significantly above or below triggers policy changes.

  **Other available data:** Bond yields, CPI-trim, CPI-median, BCPI (Bank of Canada Commodity Price Index)

### 3.4 Commodities & Energy

**Why commodities matter for TSX:** The Toronto Stock Exchange is HEAVILY weighted toward energy (~18%) and materials (~12%). When oil goes up, stocks like Suncor (SU), Cenovus (CVE), and Canadian Natural (CNQ) go up almost in lockstep. Same with gold and miners like Barrick Gold (ABX) and Agnico Eagle (AEM).

If you're swing trading Canadian stocks and you don't track commodities, you're flying blind.

| Commodity | Source | Endpoint | What It Drives |
|-----------|--------|----------|---------------|
| **WTI Crude Oil** | Alpha Vantage | `WTI` function | SU.TO, CVE.TO, CNQ.TO, IMO.TO, MEG.TO — these move almost 1:1 with oil |
| **Gold (XAU/USD)** | Alpha Vantage | `CURRENCY_EXCHANGE_RATE` XAU→USD | ABX.TO, AEM.TO, K.TO, FNV.TO, WPM.TO — gold miners track gold price |
| **Natural Gas** | Alpha Vantage | `NATURAL_GAS` function | Affects energy sector broadly, especially gas-weighted producers |
| **Copper** | Alpha Vantage | `COPPER` function | TECK.TO, FM.TO, and your CUPR holding — copper is a leading economic indicator |

**What "moves almost 1:1" means:** If oil goes up 3% today, Suncor will likely go up 2-4% today. They're highly correlated. So if you see oil breaking out, you can look at energy stocks for swing trade entries.

### 3.5 Company Fundamentals

Fundamentals tell you about a company's financial health. You don't want to swing trade a company that's about to go bankrupt, even if the chart looks good.

#### Financial Modeling Prep (FMP)
- **Website:** financialmodelingprep.com
- **Free tier:** 250 requests/day
- **What it gives you:**

  **P/E Ratio (Price-to-Earnings):**
  - Stock price divided by earnings per share.
  - A P/E of 15 means you're paying $15 for every $1 of annual earnings.
  - High P/E (>30) = market expects high growth (or stock is overvalued)
  - Low P/E (<10) = market sees problems (or stock is undervalued)
  - Why you care: Helps you avoid swing trading an absurdly overvalued stock that's due for a correction.

  **P/B Ratio (Price-to-Book):**
  - Stock price divided by book value (what the company owns minus what it owes, per share).
  - Below 1.0 = stock is trading below the value of its assets (potentially undervalued)
  - Why you care: A safety check. If P/B is extremely high, the stock has a long way to fall if sentiment shifts.

  **EPS Growth (Earnings Per Share Growth):**
  - How fast the company's profits are growing year-over-year.
  - Positive EPS growth = company is making more money = stock has fundamental support for going up.
  - Why you care: Swing trading a stock with declining earnings is risky — the "swing" might just be a dead cat bounce.

  **Debt-to-Equity Ratio:**
  - How much debt a company has compared to its equity (shareholder value).
  - Below 1.0 = healthy. Above 2.0 = heavily leveraged. Above 5.0 = danger zone.
  - Why you care: High-debt companies are fragile. One bad quarter and they can crash.

  **Revenue Trend:**
  - Is revenue going up or down quarter over quarter?
  - Why you care: A company with shrinking revenue is a trap, no matter how good the chart looks.

- **Supports TSX:** Yes, FMP covers Canadian stocks.

#### Finnhub Fundamentals
- **Included in free tier**
- **What it gives you:** Earnings dates, ESG scores, analyst ratings (buy/hold/sell consensus), basic financial metrics
- **Critical use:** **Earnings calendar**. This is non-negotiable. You MUST know when a company reports earnings because:
  - Stocks can gap up or down 10-30% overnight after an earnings report
  - A swing trade that's up 5% can turn into a 15% loss overnight if earnings are bad
  - Rule: Never enter a swing trade within 5 trading days of an earnings report

---

## 4. SNAPTRADE INTEGRATION (Portfolio Sync)

### What Is SnapTrade?

SnapTrade is a brokerage aggregation API. It connects to your Wealthsimple accounts (and 125+ other brokerages) and gives your app read access to your real portfolio data — holdings, balances, positions, transactions, and orders.

Think of it like Plaid for banks, but for investment accounts.

### Why SnapTrade?

- Wealthsimple has NO official API for developers
- SnapTrade is the proper, secure way to access your WS data
- You connect via OAuth (you log in to Wealthsimple through SnapTrade's secure portal — your password is never shared with your app)
- Auto-syncs positions and balances — no manual entry
- Free tier supports 5 brokerage connections (you only need 2)

### Free Tier Details

| Feature | Free Tier | Paid ($2/user/month) |
|---------|-----------|---------------------|
| Connections | 5 | Unlimited |
| API Requests | Unlimited | Unlimited |
| Real-time Data | Yes | Yes |
| Holdings & Balances | Yes | Yes |
| Transaction History | Yes | Yes |
| Trading | Yes (where supported) | Yes |
| Rate Limit | Default (250 req/min) | Default (250 req/min) |

5 free connections is perfect. You have 2 Wealthsimple accounts. Even if you add 2 more later, you're still within free tier.

### Setup Flow

```
1. Create free account at dashboard.snaptrade.com
2. Generate free API key (clientId + consumerKey)
3. In your app's backend:
   a. Register a SnapTrade user (represents you)
   b. Generate a Connection Portal URL
   c. Redirect to that URL in your browser
   d. Log in to Wealthsimple through the secure portal
   e. Authorize access
   f. Repeat for second Wealthsimple account
4. Your app can now pull real portfolio data via API
```

### What You Can Pull

```python
# After connecting, you can:

# Get all connected accounts
accounts = snaptrade.account_information.list_user_accounts(user_id, user_secret)
# Returns: account name, type (TFSA), balance, currency, institution

# Get holdings for each account
positions = snaptrade.account_information.get_user_account_positions(
    user_id, user_secret, account_id
)
# Returns: ticker, shares, avg cost, current price, market value, P&L

# Get account balances
balances = snaptrade.account_information.get_user_account_balance(
    user_id, user_secret, account_id
)
# Returns: cash balance, total value, buying power

# Get transaction history
activities = snaptrade.transactions_and_reporting.get_activities(
    user_id, user_secret, account_id
)
# Returns: buy/sell history, dividends received, dates, amounts
```

### Sync Strategy

| Data | Frequency | Why |
|------|-----------|-----|
| Holdings & Balances | Every 30 min during market hours | Keep portfolio view current |
| Holdings & Balances | Once at 4:30 PM ET | Final end-of-day sync |
| Transaction History | Once daily at 5:00 PM ET | Catch any new trades |
| Account Info | Once daily at 6:00 AM ET | Check for account changes |

### Architecture

```
[Your Vue Frontend] 
    ↓ calls your API
[Your FastAPI Backend] 
    ↓ calls SnapTrade SDK
[SnapTrade API] 
    ↓ connects to
[Wealthsimple servers]
    ↓ returns
[Your real holdings, balances, transactions]
    ↓ stored in
[Your PostgreSQL database]
```

Your app NEVER talks to Wealthsimple directly. SnapTrade handles all the authentication and data fetching. Your backend just calls SnapTrade's Python SDK.

---

## 5. WEALTHSIMPLE-SPECIFIC LOGIC

### 5.1 FX Cost Engine

This is CRITICAL and unique to your setup.

**The problem:** Wealthsimple charges 1.5% foreign exchange fee every time you convert between CAD and USD. When you buy a US stock, your CAD gets converted to USD (1.5% fee). When you sell that US stock, the USD gets converted back to CAD (another 1.5% fee). Total round-trip cost: **3%**.

**Why this matters for swing trading:** If you swing trade a US stock and make a 5% gain, your actual gain after FX fees is only 2%. That's terrible risk/reward. Your stop-loss might be 3% below entry, so after FX you're risking 6% to make 2%. The math doesn't work.

**The solution in the app:**

Every trade plan for a US stock will automatically calculate and show:

```
Example: Buying AAPL at $200 USD

Entry: $200.00 USD
Target 1: $212.00 USD (+6.0%)
Stop Loss: $194.00 USD (-3.0%)

WITHOUT FX AWARENESS:
  Risk: -3.0%
  Reward: +6.0%
  R/R Ratio: 2.0:1 ← looks fine

WITH FX AWARENESS (no USD account):
  FX Cost: -3.0% (round trip)
  Adjusted Risk: -6.0% (3% loss + 3% FX)
  Adjusted Reward: +3.0% (6% gain - 3% FX)
  True R/R Ratio: 0.5:1 ← TERRIBLE, do not take this trade

  ⚠️ FX WARNING: Net gain after fees is only 3%.
  💡 SUGGESTION: Look for TSX alternative or require >10% target for US stocks.
```

**The FX cost model is stored in the database** (see Trading Rules section) so you can update it if:
- Wealthsimple changes their FX fee
- You upgrade to Wealthsimple Plus (gets you a USD account, eliminating FX on US trades)
- You switch brokers

### 5.2 Account Awareness

The app knows about both your accounts and treats them appropriately:

| Account | Owner | Type | Tax Treatment | Suggested Use |
|---------|-------|------|---------------|---------------|
| TFSA #1 | Kripal | TFSA | All gains are 100% tax-free | Primary swing trading account — every dollar of profit is yours |
| TFSA #2 | Sushma | TFSA | All gains are 100% tax-free | Can be secondary trading or long-term holds |

**Why TFSA is perfect for swing trading:** In a regular (non-registered) account, you'd pay capital gains tax on every profitable trade. In a TFSA, gains are completely tax-free. This means your swing trading profits compound faster because the government isn't taking a cut.

**TFSA Contribution Room:** The app should track remaining TFSA contribution room and warn you if a deposit would exceed it. Over-contributing to a TFSA results in a 1% per month penalty tax.

### 5.3 TSX Focus Universe (50+ Tickers)

This is the list of stocks the scanner monitors daily. It's stored in the database so you can add/remove tickers anytime.

**Energy (10 tickers) — Why:** TSX is ~18% energy. These move with oil/gas prices.
- SU.TO (Suncor) — integrated oil, Canada's biggest
- CNQ.TO (Canadian Natural) — largest natural gas producer
- CVE.TO (Cenovus) — oil sands
- ENB.TO (Enbridge) — pipelines, big dividend
- TRP.TO (TC Energy) — pipelines, infrastructure
- PPL.TO (Pembina Pipeline) — midstream
- IMO.TO (Imperial Oil) — Exxon subsidiary
- MEG.TO (MEG Energy) — oil sands pure play
- WCP.TO (Whitecap Resources) — light oil
- ARX.TO (ARC Resources) — diversified energy

**Banks & Financials (11 tickers) — Why:** TSX is ~30% financials. Banks are rate-sensitive (BoC rate changes affect them directly).
- RY.TO (Royal Bank) — Canada's largest bank
- TD.TO (TD Bank) — big US exposure
- BNS.TO (Bank of Nova Scotia) — international focus
- BMO.TO (Bank of Montreal) — diversified
- CM.TO (CIBC) — domestic focus
- NA.TO (National Bank) — Quebec-focused, growing
- MFC.TO (Manulife) — insurance/wealth management
- SLF.TO (Sun Life) — insurance/asset management
- GWO.TO (Great-West Lifeco) — insurance
- POW.TO (Power Corp) — financial conglomerate
- IFC.TO (Intact Financial) — P&C insurance

**Mining & Materials (9 tickers) — Why:** TSX is ~12% materials. These move with gold, copper, potash.
- ABX.TO (Barrick Gold) — world's second-largest gold miner
- AEM.TO (Agnico Eagle) — gold miner, strong ops
- NTR.TO (Nutrien) — world's largest potash producer
- FM.TO (First Quantum) — copper miner
- TECK.TO (Teck Resources) — diversified mining
- FNV.TO (Franco-Nevada) — gold royalty/streaming
- WPM.TO (Wheaton Precious Metals) — precious metals streaming
- K.TO (Kinross Gold) — gold miner
- LUN.TO (Lundin Mining) — base metals

**Industrials & Transport (7 tickers) — Why:** Economically sensitive, good swing trade setups.
- CP.TO (Canadian Pacific Kansas City) — railway
- CNR.TO (CN Rail) — railway
- WFG.TO (West Fraser Timber) — lumber
- TIH.TO (Toromont) — equipment dealer
- SJ.TO (Stella-Jones) — utility poles, ties
- CAE.TO (CAE) — flight simulation
- WSP.TO (WSP Global) — engineering consulting

**Tech & Telecom (6 tickers) — Why:** Growth + stable sectors.
- SHOP.TO (Shopify) — e-commerce platform, TSX's largest tech stock
- CSU.TO (Constellation Software) — software conglomerate
- OTEX.TO (Open Text) — enterprise software
- T.TO (Telus) — telecom
- BCE.TO (BCE) — telecom
- RCI-B.TO (Rogers) — telecom/media

**Real Estate & Utilities (7 tickers) — Why:** Rate-sensitive, good for sector rotation plays.
- BAM.TO (Brookfield Asset Management) — alternative assets
- BN.TO (Brookfield Corporation) — parent company
- FTS.TO (Fortis) — utility, stable dividend
- EMA.TO (Emera) — utility
- AQN.TO (Algonquin Power) — renewable utility
- REI-UN.TO (RioCan REIT) — retail real estate
- CAR-UN.TO (Canadian Apartment Properties REIT) — residential

**ETFs for Sector Rotation Tracking (12 tickers) — Why:** By tracking sector ETFs, you can see where money is flowing in/out.
- XIU.TO — iShares S&P/TSX 60 (large cap TSX)
- XIC.TO — iShares Core S&P/TSX (broad TSX)
- XEI.TO — iShares S&P/TSX Composite High Dividend (you own this)
- VFV.TO — Vanguard S&P 500 Index ETF (you own this, largest holding)
- VDY.TO — Vanguard FTSE Canadian High Dividend Yield (you own this)
- ZEB.TO — BMO Equal Weight Banks
- XEG.TO — iShares S&P/TSX Capped Energy
- XGD.TO — iShares S&P/TSX Global Gold
- XMA.TO — iShares S&P/TSX Capped Materials
- ZSP.TO — BMO S&P 500 Index ETF
- XIT.TO — iShares S&P/TSX Capped Information Technology
- ZRE.TO — BMO Equal Weight REITs

---

## 6. DATABASE SCHEMA

### 6.1 Trading Rules (Database-Driven — NOT Hardcoded)

Instead of hardcoding trading rules into the application code, ALL rules live in the database. This means you can change any rule through the app's settings screen without touching code.

```sql
-- Trading rules stored as configurable key-value pairs
-- Every rule has a description so you (or future users) understand what it does
CREATE TABLE trading_rules (
    id SERIAL PRIMARY KEY,
    rule_key VARCHAR(100) UNIQUE NOT NULL,       -- unique identifier
    rule_value VARCHAR(500) NOT NULL,            -- the value (number, boolean, JSON, etc.)
    rule_type VARCHAR(20) NOT NULL,              -- "number", "boolean", "percentage", "json", "integer"
    category VARCHAR(50) NOT NULL,               -- "risk", "scanner", "trading", "fx", "portfolio", "notification"
    display_name VARCHAR(200) NOT NULL,          -- human-readable name for the settings UI
    description TEXT NOT NULL,                    -- detailed explanation of what this rule does
    min_value VARCHAR(50),                       -- minimum allowed value (for validation)
    max_value VARCHAR(50),                       -- maximum allowed value (for validation)
    is_active BOOLEAN DEFAULT TRUE,              -- can disable a rule without deleting it
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by VARCHAR(100)                       -- who changed it last
);
```

### 6.2 Default Trading Rules (What Gets Inserted on First Setup)

```sql
-- ==================== RISK MANAGEMENT RULES ====================

INSERT INTO trading_rules (rule_key, rule_value, rule_type, category, display_name, description, min_value, max_value) VALUES

('risk_per_trade_pct', '1.0', 'percentage', 'risk',
 'Risk Per Trade (%)',
 'The maximum percentage of your total account balance you can lose on a single trade. At 1%, if your account is $7,000, the most you can lose on one trade is $70. This controls your position size — the higher this number, the more shares you buy, and the more you lose if the trade goes against you. Professional traders typically use 0.5-2%. Never go above 2% with a small account.',
 '0.25', '3.0'),

('min_risk_reward_ratio', '2.0', 'number', 'risk',
 'Minimum Risk/Reward Ratio',
 'The minimum ratio of potential profit to potential loss. At 2.0, you only take trades where your target profit is at least 2x your stop-loss distance. Example: if your stop-loss is $2 below entry, your target must be at least $4 above entry. This ensures that even if you only win 40% of your trades, you still make money overall. A 2:1 ratio means you need to win just 34% of trades to break even.',
 '1.5', '5.0'),

('max_active_trades', '5', 'integer', 'risk',
 'Maximum Active Trades',
 'The maximum number of swing trades you can have open at the same time. This prevents overtrading. With 5 active trades at 1% risk each, your maximum total risk is 5% of your account. If all 5 hit stop-loss simultaneously (rare but possible), you lose 5% — survivable. Going beyond 5 with a small account spreads your capital too thin and makes each position too small to be meaningful.',
 '1', '10'),

('max_sector_exposure_pct', '30.0', 'percentage', 'risk',
 'Maximum Sector Exposure (%)',
 'The maximum percentage of your total portfolio that can be in any single sector. At 30%, if your portfolio is $10,000, no more than $3,000 can be in energy stocks. This prevents sector concentration risk — if oil crashes and 80% of your portfolio is energy stocks, you get destroyed. Diversification across sectors is your best defense against sector-specific events.',
 '15.0', '50.0'),

('max_single_position_pct', '15.0', 'percentage', 'risk',
 'Maximum Single Position (%)',
 'The maximum percentage of your portfolio that any single stock can represent. ETFs like VFV are exempt from this rule (they are already diversified). At 15%, if your portfolio is $10,000, no single stock can be worth more than $1,500. This prevents a single stock collapse from destroying your portfolio.',
 '5.0', '25.0'),

('max_portfolio_risk_pct', '6.0', 'percentage', 'risk',
 'Maximum Total Portfolio Risk (%)',
 'The maximum combined risk across ALL open trades. If each trade risks 1% and you have 5 trades, total risk is 5%. This is a circuit breaker — if total risk exceeds this, no new trades are allowed until some close. This protects against correlated losses (e.g., all your trades are in stocks that drop together during a market selloff).',
 '3.0', '10.0'),

-- ==================== SCANNER RULES ====================

('scanner_min_market_cap', '2000000000', 'number', 'scanner',
 'Minimum Market Cap ($)',
 'The minimum market capitalization (in dollars) for a stock to appear in scan results. Set to $2 billion to exclude penny stocks and micro-caps. Small stocks are easily manipulated, have wide bid-ask spreads, and can be illiquid (hard to sell when you need to). $2B+ ensures you are trading established companies with real volume.',
 '500000000', '50000000000'),

('scanner_sma_period', '50', 'integer', 'scanner',
 'Uptrend SMA Period',
 'The Simple Moving Average period used to determine if a stock is in an uptrend. At 50, the scanner requires price to be above the 50-day SMA. The 50-day SMA is the standard "medium-term trend" indicator. Price above it = uptrend (we want to buy). Price below it = downtrend (we stay away). You could change this to 20 for shorter-term trends or 200 for longer-term only.',
 '10', '200'),

('scanner_rsi_oversold', '30', 'integer', 'scanner',
 'RSI Oversold Level',
 'RSI (Relative Strength Index) level that indicates a stock is oversold. RSI ranges from 0-100. Below 30 means the stock has been sold heavily and might be due for a bounce. The scanner looks for stocks with RSI between this value and rsi_upper_bound (pullback in an uptrend) or RSI crossing above this value (reversal signal).',
 '15', '40'),

('scanner_rsi_upper_bound', '50', 'integer', 'scanner',
 'RSI Upper Bound',
 'The upper RSI limit for the pullback filter. The scanner looks for RSI between oversold (30) and this value (50). RSI of 30-50 in a stock that is above its 50-day SMA means: the stock is in an uptrend but has pulled back. This is the ideal entry for a swing trade — buying the dip in an uptrending stock.',
 '40', '60'),

('scanner_volume_multiplier', '1.5', 'number', 'scanner',
 'Volume Spike Multiplier',
 'How much higher than average volume must be to trigger a signal. At 1.5x, volume must be 50% above the 20-day average. High volume confirms that the price move has conviction — lots of buyers are coming in. A price move on low volume is suspicious and often reverses. Some traders use 2.0x for stronger confirmation.',
 '1.0', '3.0'),

('scanner_min_price', '2.0', 'number', 'scanner',
 'Minimum Stock Price ($)',
 'Minimum price per share. Stocks under $2 are often penny stocks or companies in financial trouble. They have wide spreads and low liquidity. Keep this at $2+ for safety.',
 '1.0', '20.0'),

('scanner_min_avg_volume', '100000', 'integer', 'scanner',
 'Minimum Average Daily Volume',
 'Minimum 20-day average daily volume in shares. Stocks that trade fewer than 100,000 shares per day are illiquid — you might not be able to sell when you need to, or the spread (difference between buy and sell price) could eat your profits.',
 '10000', '1000000'),

-- ==================== TRADE EXECUTION RULES ====================

('trade_max_hold_days', '10', 'integer', 'trading',
 'Maximum Hold Period (trading days)',
 'If a trade has not hit its target or stop-loss within this many trading days, it is flagged for review. Swing trades should resolve relatively quickly. A trade that sits sideways for 10+ days is tying up capital that could be used for better opportunities. You can then decide to exit, adjust targets, or extend.',
 '5', '20'),

('trade_entry_buffer_pct', '1.0', 'percentage', 'trading',
 'Entry Buffer (%)',
 'How far above the current price to set the top of the entry zone. At 1.0%, if current price is $50, the entry zone is $50.00-$50.50. This gives you a small window to enter without chasing the price too high. A larger buffer gives more flexibility but might result in a worse average entry price.',
 '0.5', '3.0'),

('trade_stop_atr_multiplier', '1.5', 'number', 'trading',
 'Stop-Loss ATR Multiplier',
 'How many ATRs (Average True Range) below entry to place the stop-loss. ATR measures how much a stock typically moves in a day. At 1.5x ATR, if a stock moves $2/day on average, your stop-loss is $3 below entry. This gives the trade enough room to breathe without getting stopped out by normal daily noise. 1.0x = tight stop (stopped out more often). 2.0x = wide stop (fewer false stops but bigger losses when hit).',
 '1.0', '3.0'),

('trade_target1_atr_multiplier', '3.0', 'number', 'trading',
 'Target 1 ATR Multiplier',
 'How many ATRs above entry to set the first profit target. At 3.0x with a 1.5x stop, your risk/reward is 2:1. This is the conservative target — where you take partial profit. Many traders sell half their position at Target 1 and let the rest run to Target 2.',
 '2.0', '5.0'),

('trade_target2_atr_multiplier', '4.5', 'number', 'trading',
 'Target 2 ATR Multiplier',
 'How many ATRs above entry to set the second profit target. At 4.5x with a 1.5x stop, your risk/reward is 3:1. This is the stretch target — where you close the remaining position. If the stock keeps running past Target 2, great — but having a defined exit prevents greed from turning a winner into a loser.',
 '3.0', '8.0'),

('earnings_blackout_days', '5', 'integer', 'trading',
 'Earnings Blackout Period (trading days)',
 'No new swing trades are allowed within this many trading days of a companys earnings report. Earnings are binary events — the stock can gap up or down 10-30% overnight regardless of what the chart says. A swing trade that is up 5% can turn into a 15% loss overnight. This rule protects you from gambling on earnings. Set to 5 trading days (1 week) to be safe.',
 '3', '15'),

-- ==================== FX / WEALTHSIMPLE RULES ====================

('fx_fee_per_conversion_pct', '1.5', 'percentage', 'fx',
 'Wealthsimple FX Fee Per Conversion (%)',
 'The foreign exchange fee Wealthsimple charges each time they convert between CAD and USD. Currently 1.5%. A round-trip (buy US stock then sell) costs 3.0% total. Update this if Wealthsimple changes their fee or if you switch brokers.',
 '0', '5.0'),

('has_usd_account', 'false', 'boolean', 'fx',
 'Has USD Account (Wealthsimple Plus)',
 'Whether you have a USD sub-account through Wealthsimple Plus ($10/month). If true, FX cost is calculated as 0% for US trades (since you pre-convert once and trade in USD). If false, the full 3% round-trip FX cost is applied to every US trade plan.',
 NULL, NULL),

('fx_warning_threshold_pct', '3.0', 'percentage', 'fx',
 'FX Warning Threshold (%)',
 'If a US stock trade plans net gain after FX fees is below this percentage, show an FX WARNING badge on the trade plan. At 3.0%, any US trade where the target gain minus 3% FX is less than 3% net will get flagged. This helps you avoid US trades where fees eat most of your profit.',
 '1.0', '5.0'),

('us_trade_min_target_pct', '8.0', 'percentage', 'fx',
 'Minimum Target % for US Trades',
 'The minimum gross target gain percentage required for a US stock trade (when you dont have a USD account). Since FX costs 3% round trip, a 5% target only nets 2%. This rule requires US targets to be at least 8% to ensure meaningful profit after fees. TSX trades are not affected by this rule.',
 '5.0', '15.0'),

-- ==================== PORTFOLIO RULES ====================

('etf_exempt_from_position_limit', 'true', 'boolean', 'portfolio',
 'ETFs Exempt From Position Limit',
 'Whether broad-market ETFs (like VFV, XIU, XIC) are exempt from the max single position percentage rule. ETFs are already diversified — VFV holds 500 stocks — so having 33% of your portfolio in VFV is fundamentally different from having 33% in one stock like NKE. Recommended: true.',
 NULL, NULL),

('portfolio_rebalance_alert_pct', '5.0', 'percentage', 'portfolio',
 'Rebalance Alert Threshold (%)',
 'If any holding drifts more than this percentage from its target allocation, trigger a rebalance alert. For example, if your target for energy is 20% and actual is 26%, and threshold is 5%, you get an alert because 26-20 = 6% > 5%. Set to 0 to disable rebalance alerts.',
 '0', '15.0'),

-- ==================== NOTIFICATION RULES ====================

('notify_stop_warning_pct', '1.5', 'percentage', 'notification',
 'Stop-Loss Warning Distance (%)',
 'Send a Telegram alert when price is within this percentage of the stop-loss. At 1.5%, if your stop is $48.50, you get warned when price drops to ~$49.23. This gives you time to decide: hold and let the stop trigger, or manually exit early.',
 '0.5', '5.0'),

('notify_daily_summary_time', '16:45', 'string', 'notification',
 'Daily Summary Time (ET)',
 'Time in Eastern Time to send the daily summary via Telegram. Default 4:45 PM — 15 minutes after market close. Allows final prices to settle.',
 NULL, NULL),

('notify_morning_briefing_time', '09:15', 'string', 'notification',
 'Morning Briefing Time (ET)',
 'Time in Eastern Time to send the morning briefing via push notification. Default 9:15 AM — 15 minutes before market open. Gives you time to review scan results and decide on trades.',
 NULL, NULL);
```

### 6.3 Core Data Tables

```sql
-- ==================== ACCOUNTS & PORTFOLIO ====================

-- Brokerage accounts (synced via SnapTrade)
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    snaptrade_account_id VARCHAR(100) UNIQUE,    -- SnapTrade's ID for this account
    snaptrade_connection_id VARCHAR(100),         -- SnapTrade connection/authorization ID
    name VARCHAR(100) NOT NULL,                   -- "Kripal TFSA", "Sushma TFSA"
    institution VARCHAR(50) DEFAULT 'wealthsimple',
    account_type VARCHAR(20),                     -- "TFSA", "RRSP", "Personal"
    account_number VARCHAR(50),                   -- masked account number from SnapTrade
    currency VARCHAR(3) DEFAULT 'CAD',
    cash_balance DECIMAL(12,2) DEFAULT 0,         -- available cash
    total_value DECIMAL(12,2) DEFAULT 0,          -- total portfolio value
    buying_power DECIMAL(12,2) DEFAULT 0,         -- how much you can buy
    contribution_room DECIMAL(12,2),              -- TFSA remaining room (manual entry)
    is_active BOOLEAN DEFAULT TRUE,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Holdings (synced via SnapTrade, enriched by our app)
CREATE TABLE holdings (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    snaptrade_position_id VARCHAR(100),
    ticker VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) NOT NULL,                -- "TSX", "NYSE", "NASDAQ"
    name VARCHAR(200),                            -- full company/ETF name
    shares DECIMAL(12,4) NOT NULL,
    avg_cost_per_share DECIMAL(10,4),             -- average cost basis
    current_price DECIMAL(10,4),
    market_value DECIMAL(12,2),                   -- shares * current_price
    book_value DECIMAL(12,2),                     -- shares * avg_cost
    unrealized_pnl DECIMAL(12,2),                 -- market_value - book_value
    unrealized_pnl_pct DECIMAL(8,2),              -- percentage gain/loss
    currency VARCHAR(3),                          -- "CAD" or "USD"
    sector VARCHAR(50),
    asset_type VARCHAR(20),                       -- "stock", "etf", "leveraged_etf"
    is_us_stock BOOLEAN DEFAULT FALSE,            -- quick flag for FX cost
    fx_cost_applied DECIMAL(8,2) DEFAULT 0,       -- total FX cost paid
    portfolio_weight_pct DECIMAL(6,2),            -- what % of total portfolio this is
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ==================== WATCHLIST & SCANNING ====================

-- Ticker universe (what the scanner monitors)
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
    is_active BOOLEAN DEFAULT TRUE,              -- disable without deleting
    notes TEXT,
    added_at TIMESTAMP DEFAULT NOW()
);

-- Scanner results
CREATE TABLE scan_results (
    id SERIAL PRIMARY KEY,
    scan_date DATE NOT NULL,
    scan_time TIMESTAMP NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    exchange VARCHAR(10),
    current_price DECIMAL(10,4),
    signal_type VARCHAR(50) NOT NULL,            -- see Signal Types section below
    signal_strength DECIMAL(4,2),                -- 0.0 to 1.0 confidence score
    rsi_14 DECIMAL(6,2),
    macd_histogram DECIMAL(10,4),
    volume_ratio DECIMAL(6,2),                   -- today's volume / 20-day avg
    above_sma_50 BOOLEAN,
    atr_14 DECIMAL(10,4),
    relative_strength DECIMAL(8,2),              -- vs index
    sector VARCHAR(50),
    notes TEXT,
    has_trade_plan BOOLEAN DEFAULT FALSE,        -- whether a plan was generated
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== TRADE PLANS & EXECUTION ====================

-- Trade plans (the actionable output)
CREATE TABLE trade_plans (
    id SERIAL PRIMARY KEY,
    scan_result_id INTEGER REFERENCES scan_results(id),
    ticker VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    sector VARCHAR(50),
    asset_type VARCHAR(20),

    -- Prices
    price_at_generation DECIMAL(10,4),           -- price when plan was created
    entry_low DECIMAL(10,4),                     -- bottom of entry zone
    entry_high DECIMAL(10,4),                    -- top of entry zone
    stop_loss DECIMAL(10,4),
    target_1 DECIMAL(10,4),
    target_2 DECIMAL(10,4),

    -- Risk calculations
    risk_per_share DECIMAL(10,4),                -- entry - stop_loss
    reward_per_share_t1 DECIMAL(10,4),           -- target_1 - entry
    reward_per_share_t2 DECIMAL(10,4),           -- target_2 - entry
    risk_reward_ratio_t1 DECIMAL(4,2),           -- reward_t1 / risk
    risk_reward_ratio_t2 DECIMAL(4,2),           -- reward_t2 / risk
    risk_amount DECIMAL(10,2),                   -- dollar amount at risk (1% of account)
    position_size_dollars DECIMAL(10,2),         -- total position value
    position_size_shares DECIMAL(10,4),          -- number of shares to buy

    -- FX impact (for US stocks)
    fx_cost_round_trip_pct DECIMAL(4,2),         -- 0 for TSX, 3.0 for US
    gross_target_pct_t1 DECIMAL(6,2),            -- % gain before FX
    net_target_pct_t1 DECIMAL(6,2),              -- % gain after FX
    fx_warning BOOLEAN DEFAULT FALSE,            -- true if net gain < threshold

    -- Fundamentals snapshot
    pe_ratio DECIMAL(8,2),
    pb_ratio DECIMAL(8,2),
    debt_to_equity DECIMAL(8,2),
    eps_growth_pct DECIMAL(8,2),
    
    -- Earnings safety
    next_earnings_date DATE,
    earnings_days_away INTEGER,
    earnings_blackout BOOLEAN DEFAULT FALSE,     -- true if too close to earnings

    -- Macro context at time of plan
    oil_price DECIMAL(8,2),
    gold_price DECIMAL(10,2),
    usd_cad DECIMAL(8,4),
    boc_rate DECIMAL(4,2),

    -- Technical snapshot
    rsi_14 DECIMAL(6,2),
    macd_histogram DECIMAL(10,4),
    ema_9 DECIMAL(10,4),
    ema_21 DECIMAL(10,4),
    sma_50 DECIMAL(10,4),
    sma_200 DECIMAL(10,4),
    atr_14 DECIMAL(10,4),
    volume_ratio DECIMAL(6,2),
    bb_position VARCHAR(20),                     -- "below_middle", "at_lower", etc.
    relative_strength_vs_index DECIMAL(8,2),

    -- Signal
    signal_type VARCHAR(50),
    signal_description TEXT,

    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending',        -- pending, active, partial_fill, hit_t1, hit_t2, stopped, expired, cancelled
    account_id INTEGER REFERENCES accounts(id),  -- which account it was executed in
    actual_entry_price DECIMAL(10,4),            -- what you actually paid
    actual_entry_date TIMESTAMP,
    actual_exit_price DECIMAL(10,4),
    actual_exit_date TIMESTAMP,
    actual_shares DECIMAL(10,4),
    actual_pnl DECIMAL(10,2),
    actual_pnl_pct DECIMAL(6,2),
    hold_days INTEGER,

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Trade execution log (tracks partial fills, scaling in/out)
CREATE TABLE trade_executions (
    id SERIAL PRIMARY KEY,
    trade_plan_id INTEGER REFERENCES trade_plans(id) ON DELETE CASCADE,
    action VARCHAR(10) NOT NULL,                 -- "buy", "sell"
    shares DECIMAL(10,4) NOT NULL,
    price DECIMAL(10,4) NOT NULL,
    total_value DECIMAL(10,2),
    reason VARCHAR(50),                          -- "entry", "target_1", "target_2", "stop_loss", "manual_exit", "expiry_exit"
    executed_at TIMESTAMP DEFAULT NOW()
);

-- ==================== TRADE HISTORY & PERFORMANCE ====================

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
    result VARCHAR(20),                          -- "win", "loss", "breakeven"
    exit_reason VARCHAR(50),                     -- "target_1", "target_2", "stop_loss", "manual", "expiry"
    risk_reward_achieved DECIMAL(4,2),           -- actual R/R
    entered_at TIMESTAMP,
    exited_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== MARKET DATA ====================

-- Daily market snapshot
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
    vix DECIMAL(6,2),                            -- volatility index (fear gauge)
    created_at TIMESTAMP DEFAULT NOW()
);

-- Sector performance tracking
CREATE TABLE sector_performance (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    sector VARCHAR(50) NOT NULL,
    etf_ticker VARCHAR(20),
    etf_price DECIMAL(10,2),
    performance_1d DECIMAL(6,2),                 -- 1-day return %
    performance_5d DECIMAL(6,2),                 -- 5-day (1 week) return %
    performance_20d DECIMAL(6,2),                -- 20-day (1 month) return %
    relative_strength_vs_tsx DECIMAL(6,2),       -- how this sector is doing vs TSX composite
    volume_ratio DECIMAL(6,2),                   -- volume vs 20-day avg
    money_flow VARCHAR(20),                      -- "inflow", "outflow", "neutral"
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(date, sector)
);

-- ==================== ALERTS ====================

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,             -- "entry_signal", "stop_warning", "stop_hit", "target_hit", "earnings_warning", "daily_summary", "fx_warning", "rule_violation"
    severity VARCHAR(20) DEFAULT 'info',         -- "critical", "high", "medium", "low", "info"
    ticker VARCHAR(20),
    trade_plan_id INTEGER REFERENCES trade_plans(id),
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    sent_via VARCHAR(20),                        -- "telegram", "push", "both"
    telegram_message_id VARCHAR(50),             -- for tracking delivery
    sent_at TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== USER PREFERENCES ====================

CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    category VARCHAR(50),                        -- "display", "notification", "account"
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Default preferences
INSERT INTO user_preferences (key, value, category) VALUES
('theme', 'dark', 'display'),
('default_chart_period', '3M', 'display'),
('telegram_enabled', 'true', 'notification'),
('push_enabled', 'true', 'notification'),
('scanner_auto_run', 'true', 'scanner'),
('show_usd_in_cad', 'true', 'display');
```

---

## 7. TRADING RULES ENGINE

The backend reads all rules from the `trading_rules` table at startup and caches them. When any service needs a rule value, it calls the rules engine:

```python
# Example usage in code:
class TradingRulesEngine:
    """
    All trading rules are read from the database.
    No trading parameters are hardcoded anywhere in the application.
    Rules are cached and refreshed every 5 minutes or on-demand.
    """
    
    def get_rule(self, rule_key: str) -> any:
        """Get a rule value by key, with type conversion."""
        # Returns typed value: float, int, bool, etc.
    
    def get_rules_by_category(self, category: str) -> dict:
        """Get all rules in a category (e.g., 'risk', 'scanner')."""
    
    def update_rule(self, rule_key: str, new_value: str, updated_by: str):
        """Update a rule value, log the change, refresh cache."""
    
    def validate_trade(self, trade_plan) -> list[str]:
        """
        Run all rules against a trade plan.
        Returns list of violations (empty = trade is valid).
        Example violations:
        - "Risk/reward ratio 1.5 is below minimum 2.0"
        - "Max active trades (5) reached"
        - "Earnings in 3 days (blackout is 5 days)"
        - "Sector exposure would exceed 30% (current: 28%, new: 34%)"
        - "Net gain after FX is only 2.1% (warning threshold: 3.0%)"
        """
    
    def get_rules_for_settings_ui(self) -> list[dict]:
        """Return all rules formatted for the Settings screen."""
```

**Why database-driven rules matter:**
1. You can tweak risk per trade from 1% to 1.5% without redeploying code
2. If you go SaaS, each user can have their own rules
3. You can A/B test different rule sets (e.g., does 1% or 2% risk produce better results for your strategy?)
4. Rules changes are logged (who changed what, when)

---

## 8. BACKEND ARCHITECTURE (FastAPI)

### 8.1 Project Structure

```
swingdge-backend/
├── app/
│   ├── main.py                          # FastAPI app entry, middleware, startup
│   ├── config.py                        # Environment variables, settings
│   ├── database.py                      # PostgreSQL connection, session management
│   │
│   ├── models/                          # SQLAlchemy ORM models
│   │   ├── __init__.py
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
│   │   └── user_preference.py
│   │
│   ├── schemas/                         # Pydantic schemas (request/response validation)
│   │   ├── __init__.py
│   │   ├── portfolio.py
│   │   ├── trade.py
│   │   ├── scanner.py
│   │   ├── market.py
│   │   └── settings.py
│   │
│   ├── api/                             # REST API route handlers
│   │   ├── __init__.py
│   │   ├── portfolio.py                 # /api/portfolio/* endpoints
│   │   ├── scanner.py                   # /api/scanner/* endpoints
│   │   ├── trades.py                    # /api/trades/* endpoints
│   │   ├── market.py                    # /api/market/* endpoints
│   │   ├── alerts.py                    # /api/alerts/* endpoints
│   │   ├── dashboard.py                 # /api/dashboard endpoint
│   │   └── settings.py                  # /api/settings/* endpoints (rules, preferences)
│   │
│   ├── services/                        # Business logic (the brain)
│   │   ├── __init__.py
│   │   ├── snaptrade_service.py         # SnapTrade SDK wrapper — portfolio sync
│   │   ├── data_fetcher.py              # Twelve Data, Alpha Vantage, Finnhub API clients
│   │   ├── technical_analysis.py        # Indicator calculations (RSI, MACD, EMA, etc.)
│   │   ├── scanner_engine.py            # Market scanning logic
│   │   ├── trade_plan_generator.py      # Generate entry/stop/target/position size
│   │   ├── rules_engine.py              # Database-driven trading rules
│   │   ├── portfolio_tracker.py         # P&L, concentration, health checks
│   │   ├── fx_calculator.py             # Wealthsimple FX cost calculations
│   │   ├── sector_rotation.py           # Sector strength & money flow tracking
│   │   ├── macro_tracker.py             # BoC rate, USD/CAD, commodities
│   │   ├── earnings_checker.py          # Earnings date lookups & blackout enforcement
│   │   ├── notification_service.py      # Telegram + Push notification sender
│   │   └── cache_service.py             # API response caching (Redis or in-memory)
│   │
│   ├── jobs/                            # Scheduled tasks (APScheduler)
│   │   ├── __init__.py
│   │   ├── scheduler.py                 # Job scheduler setup
│   │   ├── morning_scan.py              # 9:45 AM — run scanner
│   │   ├── price_monitor.py             # Every 15 min — check prices vs plans
│   │   ├── portfolio_sync.py            # Every 30 min — sync via SnapTrade
│   │   ├── daily_summary.py             # 4:45 PM — send summary
│   │   ├── morning_briefing.py          # 9:15 AM — send briefing
│   │   ├── macro_update.py              # 6:00 PM — update BoC, commodities
│   │   ├── sector_update.py             # 4:30 PM — update sector rotation
│   │   └── earnings_check.py            # 8:00 AM — flag upcoming earnings
│   │
│   └── utils/
│       ├── __init__.py
│       ├── rate_limiter.py              # API rate limit tracking
│       ├── ticker_utils.py              # TSX .TO suffix handling, exchange detection
│       ├── date_utils.py                # Trading day calculations, market hours
│       └── formatters.py                # Number, currency, percentage formatting
│
├── alembic/                             # Database migrations
│   ├── versions/
│   └── env.py
├── tests/
├── requirements.txt
├── alembic.ini
├── .env                                 # API keys (NEVER commit to git)
├── .env.example                         # Template for .env
├── Dockerfile
└── docker-compose.yml                   # Local dev: app + postgres + redis
```

### 8.2 API Endpoints (Complete)

```
# ==================== PORTFOLIO ====================
GET    /api/portfolio/summary              # Overall portfolio: total value, P&L, allocation
GET    /api/portfolio/accounts             # List all accounts with balances
GET    /api/portfolio/holdings             # All holdings with live P&L and enrichment
GET    /api/portfolio/holdings/:ticker     # Single holding detail
POST   /api/portfolio/sync                 # Trigger manual SnapTrade sync
GET    /api/portfolio/health               # Portfolio health check (concentration, risk)
GET    /api/portfolio/history              # Portfolio value over time

# ==================== SCANNER ====================
POST   /api/scanner/run                    # Trigger a scan (can specify TSX-only, US-only, or all)
GET    /api/scanner/results                # Latest scan results
GET    /api/scanner/results/:date          # Scan results for a specific date
GET    /api/scanner/history                # Scan history (last 30 days)

# ==================== TRADE PLANS ====================
GET    /api/trades/plans                   # All trade plans (filterable by status)
GET    /api/trades/plans/:id               # Single trade plan with full detail
POST   /api/trades/plans                   # Create manual trade plan
POST   /api/trades/plans/generate/:ticker  # Auto-generate plan for a ticker
PATCH  /api/trades/plans/:id/status        # Update status (entered, hit_t1, stopped, etc.)
PATCH  /api/trades/plans/:id               # Update plan details
DELETE /api/trades/plans/:id               # Cancel/delete a plan

# ==================== TRADE HISTORY ====================
GET    /api/trades/history                 # All completed trades
GET    /api/trades/history/stats           # Win rate, avg gain, avg loss, total P&L
GET    /api/trades/history/by-sector       # Performance by sector
GET    /api/trades/history/by-signal       # Performance by signal type

# ==================== MARKET DATA ====================
GET    /api/market/quote/:ticker           # Live quote + all technical indicators
GET    /api/market/chart/:ticker           # OHLCV data for charting
GET    /api/market/macro                   # BoC rate, USD/CAD, oil, gold, gas, copper
GET    /api/market/sectors                 # Sector rotation dashboard
GET    /api/market/earnings/:ticker        # Next earnings date
GET    /api/market/news/:ticker            # Recent news + sentiment for a ticker

# ==================== TICKER UNIVERSE ====================
GET    /api/universe                       # All tickers in the universe
POST   /api/universe                       # Add a ticker
PATCH  /api/universe/:ticker               # Update ticker info
DELETE /api/universe/:ticker               # Remove ticker (soft delete)

# ==================== ALERTS ====================
GET    /api/alerts                         # All alerts (paginated)
GET    /api/alerts/unread                  # Unread alerts count
PATCH  /api/alerts/:id/acknowledge         # Mark alert as read
POST   /api/alerts/test                    # Send test notification (verify Telegram works)

# ==================== SETTINGS ====================
GET    /api/settings/rules                 # All trading rules (for settings UI)
GET    /api/settings/rules/:category       # Rules by category
PATCH  /api/settings/rules/:key            # Update a rule
GET    /api/settings/preferences           # User display/notification preferences
PATCH  /api/settings/preferences/:key      # Update a preference
GET    /api/settings/accounts              # SnapTrade connection status

# ==================== DASHBOARD ====================
GET    /api/dashboard                      # Everything for the main screen in one call
```

---

## 9. TECHNICAL ANALYSIS ENGINE (Detailed)

### What Is Technical Analysis?

Technical analysis is the study of price charts and patterns to predict future price movements. Instead of analyzing a company's financials (fundamental analysis), you're analyzing the behavior of buyers and sellers through price and volume data.

### Indicators We Calculate

For every ticker in the universe, every trading day, we calculate:

#### Moving Averages (Trend Direction)
- **EMA 9 (Exponential Moving Average, 9-period):** Average price over the last 9 days, but recent days are weighted more heavily. This reacts quickly to price changes. When price is above EMA 9, the very short-term trend is up.

- **EMA 21:** Same concept, 21 days. When price is above EMA 21, the short-term trend is up. The crossover of EMA 9 above EMA 21 is a bullish signal (called a "golden cross" at this timeframe).

- **SMA 50 (Simple Moving Average, 50-period):** Simple average of the last 50 closing prices. All days weighted equally. This is the KEY trend indicator — price above SMA 50 = uptrend, below = downtrend. Our scanner requires price to be above SMA 50.

- **SMA 200:** The long-term trend indicator. Price above SMA 200 = long-term bull market for this stock. Used as a filter, not a trade signal.

#### RSI (Momentum)
- **RSI 14 (Relative Strength Index, 14-period):** Measures how fast and how much price has been moving up vs down. Scale is 0-100.
  - Above 70: "Overbought" — stock has run up too fast, might pull back
  - Below 30: "Oversold" — stock has been beaten down, might bounce
  - 30-50 in an uptrend: "Pullback" — this is the sweet spot for entry
  - We look for RSI 30-50 (pullback buying opportunity) or RSI crossing above 30 (reversal)

#### MACD (Momentum & Trend)
- **MACD (Moving Average Convergence Divergence):** Calculated from two EMAs (12 and 26 period). Shows the relationship between two moving averages.
  - **MACD Line:** EMA 12 minus EMA 26
  - **Signal Line:** 9-period EMA of the MACD line
  - **Histogram:** MACD line minus signal line
  - When histogram turns from negative to positive = momentum is shifting bullish
  - We look for histogram turning positive (momentum confirmation)

#### Bollinger Bands (Volatility)
- **Bollinger Bands (20, 2):** A middle band (SMA 20) with upper and lower bands 2 standard deviations away.
  - Price near lower band = stock is relatively cheap (potential buy)
  - Price near upper band = stock is relatively expensive (might be overextended)
  - Bands squeezing together = low volatility, big move coming
  - We check that price is NOT above the upper band (avoid buying overextended stocks)

#### ATR (Volatility for Position Sizing)
- **ATR 14 (Average True Range, 14-period):** Measures how much a stock moves per day on average, including gaps. If ATR is $2.50, the stock typically moves $2.50 per day.
  - Used to set stop-loss distance: stop = entry - (ATR × 1.5)
  - Used to set targets: target = entry + (ATR × 3.0)
  - Higher ATR = more volatile stock = wider stops needed = fewer shares bought
  - This is how we ensure our position sizing adapts to each stock's volatility

#### VWAP (Fair Price)
- **VWAP (Volume Weighted Average Price):** The average price weighted by volume throughout the day. Shows the "fair value" price. Institutional traders use this — buying below VWAP is generally considered "good" and above VWAP is "expensive."

#### Volume Analysis
- **Volume Ratio:** Today's volume divided by the 20-day average volume. If ratio is 2.0, volume is double the average — strong interest.
  - We require volume > 1.5x average for a scanner signal
  - High volume confirms that the price move has conviction

#### Relative Strength
- **Relative Strength vs Index:** How the stock is performing compared to the TSX Composite (or S&P 500 for US stocks) over the last 20 days. Positive = outperforming the market. Negative = underperforming. We want stocks that are STRONGER than the market — leaders, not laggards.

---

## 10. SCANNER SYSTEM (Detailed)

### How Scanning Works

Every trading day at 9:45 AM ET (15 minutes after market open, letting the opening volatility settle):

```
Step 1: Load all tickers from ticker_universe table
Step 2: For each ticker, fetch daily OHLCV data (cached if already fetched today)
Step 3: Calculate all technical indicators
Step 4: Apply scanner filters
Step 5: Score each passing stock (signal strength 0.0-1.0)
Step 6: Sort by signal strength (strongest first)
Step 7: Store results in scan_results table
Step 8: Send push notification: "Scanner found X candidates"
```

### Signal Types

When a stock passes the scanner, it gets tagged with a signal type explaining WHY it passed:

| Signal Type | Code | What It Means |
|-------------|------|---------------|
| RSI Pullback | `RSI_PULLBACK` | Stock is in uptrend (above SMA 50) but RSI has pulled back to 30-50 range. Classic "buy the dip" setup. |
| RSI Reversal | `RSI_REVERSAL` | RSI was below 30 (oversold) and just crossed above 30. Momentum is shifting from bearish to bullish. |
| MACD Crossover | `MACD_CROSSOVER` | MACD histogram just turned from negative to positive. Momentum is flipping bullish. |
| Volume Breakout | `VOLUME_BREAKOUT` | Price broke above a resistance level on volume > 2x average. Strong buying pressure. |
| EMA Crossover | `EMA_CROSSOVER` | EMA 9 crossed above EMA 21. Short-term trend just turned bullish. |
| Bollinger Bounce | `BB_BOUNCE` | Price touched or went below the lower Bollinger Band and is now bouncing up. Mean reversion play. |
| Combo Signal | `COMBO` | Multiple signals firing at once (e.g., RSI pullback + MACD crossover + volume spike). These are the strongest setups. |

### Signal Strength Scoring

Each stock gets a composite score from 0.0 to 1.0:

```
Score components (each 0 or 1, then averaged):
- Price above SMA 50: +1
- Price above SMA 200: +1
- RSI in buy zone (30-50): +1
- MACD histogram positive and increasing: +1
- Volume above 1.5x average: +1
- EMA 9 above EMA 21: +1
- Price near lower Bollinger Band: +1
- Relative strength > 0 (beating the index): +1
- Positive news sentiment (if available): +1

Score = sum / total components
0.8-1.0 = Very Strong
0.6-0.8 = Strong
0.4-0.6 = Moderate
Below 0.4 = Doesn't pass scanner
```

---

## 11. TRADE PLAN GENERATOR (Detailed)

When you select a scanner candidate and click "Generate Trade Plan," here's what happens:

```python
def generate_trade_plan(ticker, account):
    # 1. Get current data
    price = get_current_price(ticker)
    atr = get_atr_14(ticker)
    indicators = get_all_indicators(ticker)
    fundamentals = get_fundamentals(ticker)  # P/E, debt, earnings date
    macro = get_macro_snapshot()              # oil, gold, rates
    rules = get_trading_rules()              # from database
    
    # 2. Check earnings blackout
    earnings_date = get_next_earnings(ticker)
    trading_days_away = count_trading_days(today, earnings_date)
    if trading_days_away <= rules['earnings_blackout_days']:
        return Error("Earnings blackout: reports in {trading_days_away} days")
    
    # 3. Calculate levels using database rules
    entry_low = price
    entry_high = price * (1 + rules['trade_entry_buffer_pct'] / 100)
    stop_loss = price - (atr * rules['trade_stop_atr_multiplier'])
    target_1 = price + (atr * rules['trade_target1_atr_multiplier'])
    target_2 = price + (atr * rules['trade_target2_atr_multiplier'])
    
    # 4. Calculate risk/reward
    risk_per_share = price - stop_loss
    reward_per_share = target_1 - price
    rr_ratio = reward_per_share / risk_per_share
    
    if rr_ratio < rules['min_risk_reward_ratio']:
        flag("R/R ratio {rr_ratio} is below minimum {rules['min_risk_reward_ratio']}")
    
    # 5. Position sizing
    risk_amount = account.total_value * (rules['risk_per_trade_pct'] / 100)
    shares = risk_amount / risk_per_share
    position_dollars = shares * price
    
    # 6. FX cost calculation
    if is_us_stock(ticker) and not rules['has_usd_account']:
        fx_cost_pct = rules['fx_fee_per_conversion_pct'] * 2  # round trip
        gross_gain_pct = (target_1 - price) / price * 100
        net_gain_pct = gross_gain_pct - fx_cost_pct
        
        if net_gain_pct < rules['fx_warning_threshold_pct']:
            fx_warning = True
        
        if gross_gain_pct < rules['us_trade_min_target_pct']:
            flag("US trade target {gross_gain_pct}% below minimum {rules['us_trade_min_target_pct']}%")
    
    # 7. Portfolio rule checks
    validate_max_active_trades(rules)
    validate_sector_exposure(ticker, position_dollars, rules)
    validate_position_concentration(ticker, position_dollars, rules)
    validate_total_portfolio_risk(rules)
    
    # 8. Return complete trade plan
    return TradePlan(...)
```

---

## 12. FRONTEND ARCHITECTURE

### 12.1 Key Screens & What They Show

**Dashboard (Home)**
- Total portfolio value (both accounts combined) + today's change
- Per-account breakdown
- Active trade plans (swipeable cards)
- Sector heatmap
- Macro bar (oil, gold, rates, USD/CAD)
- Alert feed (last 5 alerts)

**Scanner**
- Run Scan button (or shows auto-scan results)
- Candidate cards: ticker, signal type, strength score, current price, R/R ratio
- Filter chips: TSX only | US only | Energy | Banks | All
- Tap candidate → Generate Trade Plan
- Tap candidate → View Chart

**Portfolio**
- Tab: Kripal TFSA | Sushma TFSA | Combined
- Holdings list: ticker, shares, avg cost, current price, P&L %, P&L $
- FX warning badge on US stocks (red badge showing "-3% FX")
- Sector allocation donut chart
- "Flags" section: overconcentration warnings, earnings alerts

**Trade Plan Detail**
- Price chart with entry/stop/target lines drawn
- All trade plan fields
- Rule validation status (green checks or red warnings)
- Macro context panel
- Fundamentals panel
- Action buttons: Enter Trade | Edit Plan | Cancel

**Market**
- Sector rotation table: sector, 1d/5d/20d performance, relative strength, money flow
- Macro dashboard: BoC rate trend, oil chart, gold chart, USD/CAD chart
- Calendar: upcoming earnings for holdings + watchlist

**Trade History**
- Table of all closed trades
- Stats cards: win rate, avg win, avg loss, profit factor, largest win, largest loss
- Equity curve chart (cumulative P&L over time)
- Breakdown by sector and signal type

**Settings**
- Trading rules (all from database, editable)
- SnapTrade connection status
- Account management
- Notification preferences
- Telegram bot setup/test
- Ticker universe management (add/remove tickers)

---

## 13. NOTIFICATION SYSTEM

### Telegram Bot Setup

```
1. Open Telegram, search for @BotFather
2. Send: /newbot
3. Name: "SwingEdge Bot"
4. Username: "swingdge_bot" (or whatever is available)
5. Copy the bot token (looks like: 123456789:ABCdefGhIJKlmNoPQRsTUVwxYZ)
6. Open a chat with your new bot, send any message
7. Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
8. Find your chat_id in the response
9. Add both to your .env file
```

### Alert Types (Complete)

| Alert | Trigger | Severity | Channel | Example Message |
|-------|---------|----------|---------|-----------------|
| Entry Signal | Stock enters the entry zone of an active trade plan | HIGH | Telegram | "🟢 SU.TO entered entry zone! Current: $52.15. Plan entry: $51.80-$52.30. Ready to buy." |
| Stop Warning | Price within X% of stop-loss | HIGH | Telegram | "⚠️ TD.TO approaching stop! Current: $76.40, Stop: $76.00 (0.5% away). Review position." |
| Stop Hit | Price hit stop-loss | CRITICAL | Telegram | "🔴 STOP HIT: TD.TO at $75.98. Plan stop: $76.00. Loss: -$84.00 (-1.1%). Exit trade." |
| Target 1 Hit | Price hit first target | HIGH | Telegram | "🎯 TARGET 1 HIT: SU.TO at $55.50! Gain: +$340 (+6.5%). Consider taking partial profit." |
| Target 2 Hit | Price hit second target | HIGH | Telegram | "🎯🎯 TARGET 2 HIT: SU.TO at $57.80! Full target reached. Gain: +$570 (+10.9%). Close position." |
| Earnings Warning | Holding has earnings within blackout period | MEDIUM | Telegram | "📅 NKE earnings in 3 days (Apr 7). You hold 46.89 shares. Consider exiting swing position." |
| FX Warning | Trade plan has poor net gain after FX | MEDIUM | Telegram | "💱 FX WARNING: AAPL trade plan nets only 2.1% after 3% FX fees. Consider TSX alternative." |
| Scanner Complete | Morning scan found candidates | LOW | Push | "🔍 Morning scan complete: 4 candidates found. Top: SU.TO (RSI Pullback, strength: 0.85)" |
| Daily Summary | End of day | LOW | Telegram + Push | Full daily summary (see template in previous doc) |
| Morning Briefing | Before market open | LOW | Push | "☀️ Good morning! 3 active trades, 2 approaching entry. Markets futures: TSX +0.3%, S&P -0.1%." |
| Rule Violation | Trade would violate a trading rule | HIGH | Telegram | "🚫 RULE VIOLATION: Buying RY.TO would push bank sector to 35% (max: 30%). Trade blocked." |
| New Scan Candidate | A high-strength candidate appeared mid-day | MEDIUM | Telegram | "🔥 New signal: ENB.TO combo signal (RSI pullback + MACD crossover), strength: 0.9" |

---

## 14. SCHEDULED JOBS

| Job | Schedule | Description |
|-----|----------|-------------|
| `portfolio_sync` | Every 30 min, 9:30 AM - 4:30 PM ET, weekdays | Sync holdings and balances from SnapTrade |
| `final_sync` | 4:30 PM ET, weekdays | Final end-of-day portfolio sync |
| `morning_scan` | 9:45 AM ET, weekdays | Run full scanner on ticker universe |
| `price_monitor` | Every 15 min, 9:30 AM - 4:00 PM ET, weekdays | Check active trade prices vs entry/stop/target levels |
| `earnings_check` | 8:00 AM ET, weekdays | Check all holdings and watchlist for upcoming earnings |
| `morning_briefing` | 9:15 AM ET, weekdays | Send morning summary via push notification |
| `macro_update` | 6:00 PM ET, weekdays | Fetch BoC rate, USD/CAD, oil, gold, gas, copper |
| `sector_update` | 4:30 PM ET, weekdays | Calculate sector performance and rotation signals |
| `daily_summary` | 4:45 PM ET, weekdays | Send end-of-day summary via Telegram |
| `transaction_sync` | 5:00 PM ET, weekdays | Sync transaction history from SnapTrade |
| `cache_cleanup` | 12:00 AM ET, daily | Clear expired cache entries |
| `weekly_report` | 5:00 PM ET, Fridays | Weekly performance summary with win/loss stats |

---

## 15. CURRENT HOLDINGS (To Import at Setup)

See Section 9 of previous document — unchanged. These get imported automatically once SnapTrade is connected.

---

## 16. BUILD PHASES

### Phase 1: Foundation (Week 1-2)
**Goal:** Backend running, database set up, SnapTrade connected, basic frontend showing real portfolio data.

- [ ] Initialize FastAPI project with folder structure
- [ ] Set up PostgreSQL database + run migrations (all tables)
- [ ] Insert default trading rules into database
- [ ] Insert ticker universe (50+ TSX + ETF tickers)
- [ ] Sign up for API keys: Twelve Data, Alpha Vantage, Finnhub, FMP, Marketaux
- [ ] Implement SnapTrade SDK integration
- [ ] Connect both Wealthsimple accounts via SnapTrade portal
- [ ] Build portfolio sync service (fetch holdings, balances)
- [ ] Build data fetcher service (Twelve Data client with caching)
- [ ] Build portfolio API endpoints
- [ ] Initialize Vue 3 project with Vite + PWA + Pinia + Router
- [ ] Build Dashboard view (portfolio summary from real SnapTrade data)
- [ ] Build Portfolio view (holdings list with live P&L)

### Phase 2: Analysis Engine (Week 3-4)
**Goal:** Scanner works, generates real trade plans with all calculations.

- [ ] Implement technical indicator calculations
- [ ] Build scanner engine with all filter criteria
- [ ] Build signal strength scoring
- [ ] Build trade plan generator with position sizing
- [ ] Implement FX cost calculator
- [ ] Implement earnings date checker + blackout enforcement
- [ ] Build trading rules engine (reads from database)
- [ ] Build Scanner API endpoints
- [ ] Build Trade Plans API endpoints
- [ ] Build Settings API (rules CRUD)
- [ ] Build Scanner view in frontend
- [ ] Build Trade Plan detail view
- [ ] Build Settings view (editable rules)

### Phase 3: Market Intelligence (Week 5-6)
**Goal:** Macro data flowing, sector rotation visible, full market context.

- [ ] Implement Bank of Canada Valet API integration
- [ ] Implement commodity price tracking (oil, gold, gas, copper)
- [ ] Build sector rotation tracker
- [ ] Build relative strength calculator
- [ ] Build Market view in frontend
- [ ] Build sector heatmap component
- [ ] Add macro context to trade plans
- [ ] Build FMP + Finnhub fundamentals integration

### Phase 4: Notifications & Monitoring (Week 7-8)
**Goal:** Automated alerts working, scheduled jobs running, hands-off monitoring.

- [ ] Set up Telegram bot
- [ ] Implement notification service
- [ ] Build all alert types
- [ ] Set up APScheduler with all scheduled jobs
- [ ] Implement PWA push notifications (VAPID keys)
- [ ] Build price monitoring job
- [ ] Build morning scan job
- [ ] Build daily summary job
- [ ] Build alert feed in frontend
- [ ] Test all notification flows end-to-end

### Phase 5: Trade Tracking & History (Week 9-10)
**Goal:** Full trade lifecycle tracked, performance analytics working.

- [ ] Build trade execution logging
- [ ] Build trade lifecycle (pending → active → hit_t1 → closed)
- [ ] Implement P&L tracking for closed trades
- [ ] Build trade history view with stats
- [ ] Build performance analytics (win rate, profit factor, equity curve)
- [ ] Build portfolio health check (concentration, sector balance, risk level)
- [ ] Build risk dashboard
- [ ] Polish UI, responsive design, loading states, error handling
- [ ] End-to-end testing

### Phase 6: SaaS Prep (Future)
- [ ] Authentication (JWT or OAuth)
- [ ] Multi-user support + per-user rules
- [ ] Stripe billing integration
- [ ] Landing page
- [ ] Onboarding flow
- [ ] Admin dashboard

---

## 17. ENVIRONMENT VARIABLES

```env
# ==================== DATABASE ====================
DATABASE_URL=postgresql://user:pass@localhost:5432/swingdge

# ==================== SNAPTRADE ====================
SNAPTRADE_CLIENT_ID=your_client_id
SNAPTRADE_CONSUMER_KEY=your_consumer_key
SNAPTRADE_USER_ID=your_registered_user_id
SNAPTRADE_USER_SECRET=your_user_secret

# ==================== MARKET DATA APIs ====================
TWELVE_DATA_KEY=your_key_here
ALPHA_VANTAGE_KEY=your_key_here
FINNHUB_KEY=your_key_here
FMP_KEY=your_key_here
MARKETAUX_KEY=your_key_here

# ==================== TELEGRAM ====================
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# ==================== PWA PUSH ====================
VAPID_PUBLIC_KEY=your_public_key
VAPID_PRIVATE_KEY=your_private_key
VAPID_CLAIM_EMAIL=your_email@example.com

# ==================== REDIS (optional) ====================
REDIS_URL=redis://localhost:6379

# ==================== APP CONFIG ====================
APP_ENV=development
APP_SECRET_KEY=random_secret_for_jwt
TIMEZONE=America/Toronto
LOG_LEVEL=INFO
```

---

## 18. GLOSSARY OF TRADING TERMS

For reference when reading this document or the app:

| Term | Meaning |
|------|---------|
| **Swing Trade** | Buying a stock and holding for days to weeks to profit from a price "swing" |
| **Entry Zone** | The price range where you plan to buy |
| **Stop-Loss** | A price below your entry where you sell to limit losses |
| **Target** | A price above your entry where you plan to sell for profit |
| **Risk/Reward (R/R)** | Ratio of potential profit to potential loss. 2:1 means you could make 2x what you risk |
| **Position Size** | How many shares/dollars you put into a trade |
| **ATR** | Average True Range — how much a stock moves per day |
| **RSI** | Relative Strength Index — momentum indicator (0-100) |
| **MACD** | Moving Average Convergence Divergence — trend/momentum indicator |
| **EMA** | Exponential Moving Average — trend-following, weights recent prices more |
| **SMA** | Simple Moving Average — average closing price over N days |
| **Bollinger Bands** | Volatility bands above and below a moving average |
| **VWAP** | Volume Weighted Average Price — "fair value" for the day |
| **Overbought** | RSI above 70 — stock may have run too far too fast |
| **Oversold** | RSI below 30 — stock may have fallen too far too fast |
| **Pullback** | A temporary price decline within an overall uptrend |
| **Breakout** | Price moving above a resistance level with high volume |
| **Sector Rotation** | Money flowing from one sector to another (e.g., out of tech, into energy) |
| **Relative Strength** | How a stock performs compared to its benchmark index |
| **FX Cost** | Foreign exchange fee for converting CAD to USD or vice versa |
| **TFSA** | Tax-Free Savings Account — Canadian account where gains are not taxed |
| **Market Cap** | Total value of a company (share price × total shares) |
| **P/E Ratio** | Price-to-Earnings — how much you pay per dollar of earnings |
| **Earnings Report** | Quarterly financial results that can cause big price moves |
| **Volume** | Number of shares traded — confirms whether a move has conviction |
| **Liquidity** | How easily you can buy/sell without affecting the price |
| **Gap** | When a stock opens significantly higher/lower than yesterday's close |
| **Dead Cat Bounce** | A brief recovery in a falling stock that doesn't last |
| **Profit Factor** | Total gains / Total losses — above 1.0 means profitable overall |
| **Drawdown** | Peak-to-trough decline in portfolio value |
| **Equity Curve** | Chart of your cumulative P&L over time |

---

*⚠️ Disclaimer: SwingEdge is a research and tracking tool. It does not constitute financial advice. Always apply your own risk management and judgment before placing trades. Past performance of any strategy does not guarantee future results.*
