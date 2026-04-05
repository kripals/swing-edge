# SwingEdge — Swing Trading Research & Portfolio App

## Project Architecture Document

**Owner:** Kripal Shrestha
**Location:** Ontario, Canada
**Broker:** Wealthsimple (2x TFSA accounts)
**Current Portfolio:** ~$7,287 CAD across TSX + US equities/ETFs
**Monthly Contribution:** $6,000–$8,000 CAD
**Goal:** Build a personal trading research app that scans markets, generates trade plans, tracks portfolio, and sends alerts — to grow portfolio through disciplined swing trading.

---

## 1. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Vue 3 + Vite (PWA) | Kripal knows Vue; PWA gives push notifications + mobile feel for free |
| Backend | Python + FastAPI | Best ecosystem for financial data (pandas, ta-lib, numpy) |
| Database | PostgreSQL (free tier) | Structured data, good for time-series queries |
| Cache | Redis (or in-memory for MVP) | Cache API responses to stay within free tier limits |
| Task Scheduler | APScheduler (Python) | Cron jobs for daily scans, price checks, alerts |
| Notifications | Telegram Bot API | Free, instant, easy to set up, personal use |
| PWA Push | Web Push API (VAPID) | Browser/mobile push for daily summaries |
| Hosting - Frontend | Vercel (free) | Zero config Vue deployment |
| Hosting - Backend | Railway (free tier) | Backend + Postgres + cron in one place |
| Hosting - Alternative | Render.com (free tier) | Backup option if Railway limits hit |

---

## 2. API Data Sources (Priority Order)

### 2.1 Price & Technical Data (THE BACKBONE)

| API | Free Tier | Use For | Key Notes |
|-----|-----------|---------|-----------|
| **Twelve Data** (PRIMARY) | 800 req/day, 8/min | OHLCV, technicals, real-time quotes | Best free tier. Supports TSX (.TO suffix) + NYSE/NASDAQ |
| **Alpha Vantage** (BACKUP) | 25 req/day | Backup price data, commodities (WTI, gold, nat gas) | Use ONLY when Twelve Data is exhausted or for commodity endpoints |
| **Finnhub** (SUPPLEMENT) | 60 req/min | Real-time quotes, earnings calendar, company news | Generous rate limit, great for earnings dates |

**API Key Strategy:**
- Sign up for free keys at all three on day one
- Twelve Data handles 90% of daily needs
- Cache aggressively — a stock's daily candle doesn't change after market close
- TSX tickers use `.TO` suffix (e.g., `CNQ.TO`, `SU.TO`, `RY.TO`)
- US tickers use plain symbol (e.g., `NKE`, `UPS`, `AAPL`)

### 2.2 Canadian Macro Data

| API | Cost | Provides |
|-----|------|----------|
| **Bank of Canada Valet API** | FREE, no key | BoC policy rate, USD/CAD exchange rate, CPI inflation, bond yields, BCPI commodity index |

**Endpoints to implement:**
- `bankofcanada.ca/valet` — BoC overnight rate (currently tracked)
- `bankofcanada.ca/valet` — USD/CAD rate (critical for FX cost calculations)
- `bankofcanada.ca/valet` — CPI-trim, CPI-median (inflation gauges)

**Why this matters:** BoC rate directly affects Canadian banks (RY, TD, BNS) and REITs. USD/CAD tells you the real FX cost on US trades.

### 2.3 News & Sentiment

| API | Free Tier | Use For |
|-----|-----------|---------|
| **Marketaux** | 100 req/day | TSX-specific news + sentiment scores (-1 to +1) |
| **Finnhub News** | Included in free tier | Company-specific news, market news |
| **Alpha Vantage News** | Included in free key | AI sentiment scores, 15yr transcripts |

**Usage rule:** News is for CONFIRMATION and AVOIDANCE only. Never enter a trade based on sentiment alone. Use it to: avoid earnings surprises, confirm momentum, and flag sector-wide events.

### 2.4 Commodities & Energy

| Data Point | Source | Why |
|-----------|--------|-----|
| WTI Crude Oil | Alpha Vantage (`WTI` endpoint) | Drives SU, CVE, CNQ prices almost 1:1 |
| Gold (XAU/USD) | Alpha Vantage (`XAUUSD` endpoint) | Drives ABX, AEM, gold miners |
| Natural Gas | Alpha Vantage (`NATURAL_GAS` endpoint) | Affects energy sector broadly |
| Copper | Alpha Vantage | Relevant for CUPR and materials sector |

### 2.5 Company Fundamentals

| API | Free Tier | Provides |
|-----|-----------|----------|
| **Financial Modeling Prep (FMP)** | 250 req/day | P/E, P/B, EPS, revenue, debt ratios, income statements. Supports TSX |
| **Finnhub Fundamentals** | Free tier | Earnings dates, ESG scores, analyst ratings |

**Critical rule:** The app MUST check earnings dates before generating any trade plan. Hard blackout: no new swing trades within 5 trading days of an earnings report.

---

## 3. Wealthsimple-Specific Logic (BUILT INTO THE APP)

This is what makes your app different from generic trading tools.

### 3.1 FX Cost Engine

```
Every trade plan for a US stock must show:
- Raw gain/loss %
- FX cost (1.5% buy + 1.5% sell = 3% round-trip)
- Net gain/loss after FX
- Flag: "FX WARNING" if net gain < 2% after fees
- Recommendation: "Consider TSX alternative" when applicable
```

### 3.2 Account Awareness

| Account | Type | Tax Treatment | Trading Strategy |
|---------|------|---------------|-----------------|
| TFSA #1 (Kripal) | TFSA | Tax-free gains, no capital gains tax | Primary swing trading account |
| TFSA #2 (Sushma) | TFSA | Tax-free gains, no capital gains tax | Secondary / long-term holds |

**TFSA annual contribution limit:** Track remaining room. The app should warn if approaching the limit.

### 3.3 TSX Focus List (Expanded — 50+ Tickers)

**Energy:**
SU.TO, CNQ.TO, CVE.TO, ENB.TO, TRP.TO, PPL.TO, IMO.TO, MEG.TO, WCP.TO, ARX.TO

**Banks & Financials:**
RY.TO, TD.TO, BNS.TO, BMO.TO, CM.TO, NA.TO, MFC.TO, SLF.TO, GWO.TO, POW.TO, IFC.TO

**Mining & Materials:**
ABX.TO, AEM.TO, NTR.TO, FM.TO, TECK.TO, FNV.TO, WPM.TO, K.TO, LUN.TO

**Industrials & Transport:**
CP.TO, CNR.TO, WFG.TO, TIH.TO, SJ.TO, CAE.TO, WSP.TO

**Tech & Telecom:**
SHOP.TO, CSU.TO, OTEX.TO, T.TO, BCE.TO, RCI-B.TO

**Real Estate & Utilities:**
BAM.TO, BN.TO, FTS.TO, EMA.TO, AQN.TO, REI-UN.TO, CAR-UN.TO

**ETFs (for sector rotation tracking):**
XIU.TO, XIC.TO, XEI.TO, VFV.TO, VDY.TO, ZEB.TO, XEG.TO, XGD.TO, XMA.TO, ZSP.TO

---

## 4. Database Schema

### 4.1 Core Tables

```sql
-- User settings and account info
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),                    -- "Kripal TFSA", "Sushma TFSA"
    broker VARCHAR(50) DEFAULT 'wealthsimple',
    account_type VARCHAR(20),             -- "TFSA"
    currency VARCHAR(3) DEFAULT 'CAD',
    has_usd_account BOOLEAN DEFAULT FALSE,
    balance DECIMAL(12,2),
    contribution_room DECIMAL(12,2),
    updated_at TIMESTAMP
);

-- Current portfolio holdings
CREATE TABLE holdings (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    ticker VARCHAR(20),
    exchange VARCHAR(10),                 -- "TSX" or "NYSE" or "NASDAQ"
    shares DECIMAL(10,4),
    avg_cost DECIMAL(10,4),
    currency VARCHAR(3),                  -- "CAD" or "USD"
    current_price DECIMAL(10,4),
    unrealized_pnl DECIMAL(10,2),
    unrealized_pnl_pct DECIMAL(6,2),
    sector VARCHAR(50),
    added_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Watchlist / scan candidates
CREATE TABLE watchlist (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20),
    exchange VARCHAR(10),
    sector VARCHAR(50),
    added_reason TEXT,                    -- "Scanner: RSI pullback in uptrend"
    status VARCHAR(20) DEFAULT 'watching', -- watching, entry_ready, entered, expired
    created_at TIMESTAMP,
    expires_at TIMESTAMP
);

-- Trade plans (generated by the analysis engine)
CREATE TABLE trade_plans (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20),
    exchange VARCHAR(10),
    currency VARCHAR(3),
    sector VARCHAR(50),
    current_price DECIMAL(10,4),
    entry_low DECIMAL(10,4),
    entry_high DECIMAL(10,4),
    stop_loss DECIMAL(10,4),
    target_1 DECIMAL(10,4),
    target_2 DECIMAL(10,4),
    risk_reward_ratio DECIMAL(4,2),
    position_size_dollars DECIMAL(10,2),
    position_size_shares DECIMAL(10,4),
    risk_amount DECIMAL(10,2),           -- 1% of account
    fx_cost_pct DECIMAL(4,2),            -- 0 for TSX, 3.0 for US without USD acct
    net_gain_after_fx DECIMAL(6,2),      -- target gain minus FX cost
    earnings_date DATE,
    earnings_days_away INTEGER,
    signal_type VARCHAR(50),             -- "RSI_PULLBACK", "MACD_CROSSOVER", etc.
    status VARCHAR(20) DEFAULT 'pending', -- pending, active, hit_t1, hit_t2, stopped, expired
    notes TEXT,
    created_at TIMESTAMP,
    closed_at TIMESTAMP,
    closed_price DECIMAL(10,4),
    actual_pnl DECIMAL(10,2)
);

-- Completed trades (history)
CREATE TABLE trade_history (
    id SERIAL PRIMARY KEY,
    trade_plan_id INTEGER REFERENCES trade_plans(id),
    account_id INTEGER REFERENCES accounts(id),
    ticker VARCHAR(20),
    entry_price DECIMAL(10,4),
    exit_price DECIMAL(10,4),
    shares DECIMAL(10,4),
    gross_pnl DECIMAL(10,2),
    fx_cost DECIMAL(10,2),
    net_pnl DECIMAL(10,2),
    hold_days INTEGER,
    result VARCHAR(20),                  -- "win", "loss", "breakeven"
    entered_at TIMESTAMP,
    exited_at TIMESTAMP
);

-- Daily market snapshot (for sector rotation tracking)
CREATE TABLE market_snapshots (
    id SERIAL PRIMARY KEY,
    date DATE,
    tsx_composite DECIMAL(10,2),
    sp500 DECIMAL(10,2),
    usd_cad DECIMAL(8,4),
    boc_rate DECIMAL(4,2),
    wti_oil DECIMAL(8,2),
    gold DECIMAL(10,2),
    nat_gas DECIMAL(8,4),
    copper DECIMAL(8,4),
    cpi DECIMAL(4,2),
    created_at TIMESTAMP
);

-- Sector performance (for rotation signals)
CREATE TABLE sector_performance (
    id SERIAL PRIMARY KEY,
    date DATE,
    sector VARCHAR(50),
    etf_ticker VARCHAR(20),             -- XEG.TO for energy, ZEB.TO for banks, etc.
    performance_1d DECIMAL(6,2),
    performance_5d DECIMAL(6,2),
    performance_20d DECIMAL(6,2),
    relative_strength DECIMAL(6,2),     -- vs TSX composite
    volume_ratio DECIMAL(6,2),          -- vs 20-day avg
    created_at TIMESTAMP
);

-- Alerts log
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50),                    -- "entry_signal", "stop_hit", "target_hit", "earnings_warning", "daily_summary"
    ticker VARCHAR(20),
    message TEXT,
    sent_via VARCHAR(20),               -- "telegram", "push"
    sent_at TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE
);
```

---

## 5. Backend Architecture (FastAPI)

### 5.1 Project Structure

```
swingdge-backend/
├── app/
│   ├── main.py                      # FastAPI app entry
│   ├── config.py                    # API keys, DB config, settings
│   ├── database.py                  # PostgreSQL connection
│   ├── models/                      # SQLAlchemy models
│   │   ├── account.py
│   │   ├── holding.py
│   │   ├── trade_plan.py
│   │   ├── watchlist.py
│   │   └── market_snapshot.py
│   ├── api/                         # REST endpoints
│   │   ├── portfolio.py             # GET/POST holdings, account info
│   │   ├── scanner.py               # GET scan results, trigger scan
│   │   ├── trade_plans.py           # GET/POST/PATCH trade plans
│   │   ├── market.py                # GET market data, sector performance
│   │   ├── alerts.py                # GET alert history
│   │   └── dashboard.py             # GET dashboard summary
│   ├── services/                    # Business logic
│   │   ├── data_fetcher.py          # Twelve Data, Alpha Vantage, Finnhub clients
│   │   ├── technical_analysis.py    # Indicator calculations
│   │   ├── scanner_engine.py        # Market scanning logic
│   │   ├── trade_plan_generator.py  # Generate entry/stop/target
│   │   ├── portfolio_tracker.py     # P&L calculations
│   │   ├── fx_calculator.py         # Wealthsimple FX cost logic
│   │   ├── sector_rotation.py       # Sector strength tracking
│   │   ├── macro_tracker.py         # BoC, commodities
│   │   └── notification_service.py  # Telegram + Push
│   ├── jobs/                        # Scheduled tasks
│   │   ├── daily_scan.py            # Run scanner at market open
│   │   ├── price_monitor.py         # Check entry/stop/target levels
│   │   ├── daily_summary.py         # End of day report
│   │   ├── macro_update.py          # Update BoC, commodities daily
│   │   └── sector_update.py         # Update sector rotation daily
│   └── utils/
│       ├── cache.py                 # API response caching
│       ├── rate_limiter.py          # Respect API rate limits
│       └── ticker_utils.py          # TSX/US ticker formatting
├── requirements.txt
├── .env                             # API keys (NEVER commit)
└── docker-compose.yml               # Local dev setup
```

### 5.2 Key API Endpoints

```
# Portfolio
GET    /api/portfolio/summary          # Dashboard overview
GET    /api/portfolio/holdings          # All holdings with live P&L
POST   /api/portfolio/holdings          # Add/update a holding
GET    /api/portfolio/accounts          # Account info

# Scanner
GET    /api/scanner/run                 # Trigger a scan, return candidates
GET    /api/scanner/results             # Latest scan results
GET    /api/scanner/history             # Past scan results

# Trade Plans
GET    /api/trades/plans                # All active trade plans
POST   /api/trades/plans                # Create manual trade plan
PATCH  /api/trades/plans/:id            # Update status (entered, closed)
GET    /api/trades/history              # Completed trades with stats

# Market Data
GET    /api/market/quote/:ticker        # Live quote + technicals
GET    /api/market/sectors              # Sector rotation dashboard
GET    /api/market/macro                # BoC rate, USD/CAD, commodities
GET    /api/market/earnings/:ticker     # Next earnings date

# Alerts
GET    /api/alerts                      # Alert history
POST   /api/alerts/test                 # Send test notification

# Dashboard
GET    /api/dashboard                   # Everything for the main screen
```

### 5.3 Technical Analysis Engine

The scanner calculates these indicators for every ticker in the universe:

```python
# Indicators to calculate per ticker
indicators = {
    "ema_9": "9-period Exponential Moving Average",
    "ema_21": "21-period Exponential Moving Average",
    "sma_50": "50-period Simple Moving Average",
    "sma_200": "200-period Simple Moving Average",
    "rsi_14": "14-period Relative Strength Index",
    "macd": "MACD line (12, 26)",
    "macd_signal": "MACD signal line (9)",
    "macd_histogram": "MACD histogram",
    "bb_upper": "Bollinger Band upper (20, 2)",
    "bb_middle": "Bollinger Band middle (20)",
    "bb_lower": "Bollinger Band lower (20, 2)",
    "atr_14": "14-period Average True Range",
    "vwap": "Volume Weighted Average Price",
    "volume_ratio": "Current volume / 20-day avg volume",
    "relative_strength": "Performance vs TSX Composite (20-day)"
}
```

### 5.4 Scanner Filters (Buy Signal Criteria)

```python
# A stock passes the scanner if ALL of these are true:
scan_filters = {
    "uptrend": "price > SMA 50",
    "pullback": "RSI between 30-50 OR RSI just crossed above 30",
    "momentum": "MACD histogram turning positive (today > yesterday)",
    "volume": "volume > 1.5x 20-day average",
    "volatility": "ATR > minimum threshold (avoid dead stocks)",
    "market_cap": "> $2B CAD",
    "earnings_safe": "next earnings > 5 trading days away",
    "not_overextended": "price < upper Bollinger Band"
}
```

### 5.5 Trade Plan Generation Logic

```python
# For each stock that passes the scanner:
def generate_trade_plan(ticker, account):
    entry_zone = (current_price, current_price * 1.01)  # up to 1% above current
    stop_loss = current_price - (atr_14 * 1.5)           # 1.5x ATR below entry
    target_1 = current_price + (atr_14 * 3.0)            # 3x ATR (2:1 R/R)
    target_2 = current_price + (atr_14 * 4.5)            # 4.5x ATR (3:1 R/R)
    
    risk_per_share = current_price - stop_loss
    risk_amount = account.balance * 0.01                  # 1% of account
    shares = risk_amount / risk_per_share
    position_size = shares * current_price
    
    # FX cost calculation
    if exchange != "TSX" and not account.has_usd_account:
        fx_cost_pct = 3.0  # 1.5% each way
    else:
        fx_cost_pct = 0.0
    
    net_gain_t1 = ((target_1 - current_price) / current_price * 100) - fx_cost_pct
```

---

## 6. Frontend Architecture (Vue 3 PWA)

### 6.1 Project Structure

```
swingdge-frontend/
├── public/
│   ├── manifest.json                # PWA manifest
│   └── sw.js                        # Service worker for push notifications
├── src/
│   ├── App.vue
│   ├── main.js
│   ├── router/
│   │   └── index.js                 # Vue Router
│   ├── stores/                      # Pinia state management
│   │   ├── portfolio.js
│   │   ├── scanner.js
│   │   ├── trades.js
│   │   └── market.js
│   ├── views/
│   │   ├── Dashboard.vue            # Main overview screen
│   │   ├── Portfolio.vue            # Holdings + P&L
│   │   ├── Scanner.vue              # Scan results + candidates
│   │   ├── TradePlan.vue            # Individual trade plan detail
│   │   ├── Market.vue               # Sector rotation + macro
│   │   ├── TradeHistory.vue         # Past trades + stats
│   │   └── Settings.vue             # Account config, API keys
│   ├── components/
│   │   ├── HoldingCard.vue          # Single holding with P&L
│   │   ├── TradePlanCard.vue        # Trade plan summary card
│   │   ├── SectorHeatmap.vue        # Sector rotation visual
│   │   ├── MiniChart.vue            # Sparkline price chart
│   │   ├── FxWarningBadge.vue       # "FX: -3%" warning badge
│   │   ├── EarningsCountdown.vue    # Days until earnings
│   │   ├── RiskGauge.vue            # Portfolio risk level
│   │   └── AlertFeed.vue            # Recent alerts timeline
│   └── services/
│       ├── api.js                   # Axios client to backend
│       └── push.js                  # Push notification registration
├── vite.config.js
└── package.json
```

### 6.2 Key Screens

**Dashboard (Home Screen)**
- Total portfolio value + daily change
- Account breakdown (Kripal TFSA / Sushma TFSA)
- Active trade plans (cards with entry/stop/target)
- Top movers in holdings (biggest gains/losses today)
- Sector rotation heatmap (which sectors are hot/cold)
- Today's macro snapshot (BoC rate, USD/CAD, oil, gold)
- Recent alerts feed

**Scanner Screen**
- "Run Scan" button (or auto-runs at 9:45 AM ET)
- List of candidates with signal type + R/R ratio
- Quick-view technicals for each candidate
- One-tap to generate full trade plan
- Filter by: TSX only, US only, sector, signal type

**Portfolio Screen**
- All holdings grouped by account
- Each holding shows: shares, avg cost, current price, P&L %, P&L $
- FX warning badge on US positions
- Sector allocation pie chart
- "Health check" flags (overweight in one sector, concentrated positions)

**Trade Plan Detail Screen**
- Full trade plan with entry zone, stop, targets
- Mini chart with entry/stop/target lines drawn
- Fundamentals snapshot (P/E, earnings date, debt ratio)
- Relevant macro context (oil price for energy stocks, etc.)
- "Enter Trade" button to log execution
- Status tracking (watching → entered → hit T1 → closed)

---

## 7. Notification System

### 7.1 Telegram Bot Setup

```
1. Message @BotFather on Telegram
2. Create bot: /newbot → name it "SwingEdge Bot"
3. Save the bot token
4. Get your chat_id by messaging the bot and hitting:
   https://api.telegram.org/bot<TOKEN>/getUpdates
5. Store bot_token and chat_id in .env
```

### 7.2 Alert Types

| Alert | When | Channel | Priority |
|-------|------|---------|----------|
| Entry Signal | Stock hits entry zone | Telegram | HIGH |
| Stop-Loss Warning | Price within 1% of stop | Telegram | HIGH |
| Stop-Loss Hit | Price hit stop-loss | Telegram | CRITICAL |
| Target 1 Hit | Price hit first target | Telegram | HIGH |
| Target 2 Hit | Price hit second target | Telegram | HIGH |
| Earnings Warning | Holding has earnings in 5 days | Telegram | MEDIUM |
| Daily Summary | 4:30 PM ET (after market close) | Telegram + Push | LOW |
| Morning Briefing | 9:30 AM ET (market open) | Push | LOW |
| Scan Complete | Scanner found new candidates | Push | LOW |

### 7.3 Daily Summary Template

```
📊 SwingEdge Daily Summary — April 3, 2026

💼 Portfolio: $7,287.00 CAD (+$42.15 today, +0.58%)
   Kripal TFSA: $X,XXX.XX
   Sushma TFSA: $X,XXX.XX

📈 Active Trades: 3
   SU.TO: Entered $52.10 → Current $53.80 (+3.2%) — T1 at $55.50
   ENB.TO: Watching — entry zone $74.50-$75.00
   TD.TO: Entered $78.20 → Current $77.90 (-0.4%) — Stop at $76.00

🔍 Scanner: 4 new candidates found
   → Open app to review

🏭 Sector Rotation:
   🟢 Energy +1.8% | 🟢 Banks +0.9% | 🔴 Tech -1.2%

🛢️ Macro:
   Oil: $109/bbl | Gold: $2,450 | USD/CAD: 1.36 | BoC: 2.25%

📅 Earnings Watch:
   NKE reports in 3 days — CONSIDER EXITING
```

---

## 8. Scheduled Jobs

| Job | Schedule | What It Does |
|-----|----------|-------------|
| `morning_scan` | 9:45 AM ET weekdays | Run scanner on full ticker universe |
| `price_monitor` | Every 15 min during market hours | Check active trades vs entry/stop/target |
| `daily_macro_update` | 6:00 PM ET weekdays | Fetch BoC rate, USD/CAD, oil, gold |
| `sector_update` | 4:30 PM ET weekdays | Calculate sector performance + rotation |
| `daily_summary` | 4:45 PM ET weekdays | Send daily summary via Telegram |
| `earnings_check` | 8:00 AM ET weekdays | Flag holdings with earnings this week |
| `portfolio_sync` | Every 30 min during market hours | Update holdings with live prices |

---

## 9. Kripal's Current Holdings (Imported at Setup)

### Kripal TFSA + Sushma TFSA Combined:

| Ticker | Exchange | Shares | Value (CAD) | P&L % | Sector | Notes |
|--------|----------|--------|-------------|-------|--------|-------|
| VFV | TSX | 14.97 | $2,431 | +7.79% | ETF (S&P 500) | Largest holding at 33% — consider this your core |
| XEI | TSX | 20.28 | $744 | +33.17% | ETF (Dividend) | Solid dividend ETF |
| ENB | TSX | 8.33 | $628 | +23.03% | Energy | Pipeline, strong dividend |
| NKE | US | 46.89 | $915 | ~-37% | Consumer | PROBLEM — deep loss, review immediately |
| UPS | US | 3.25 | $444 | -21.83% | Industrials | PROBLEM — downtrend + FX drag |
| VDY | TSX | 7.33 | $494 | +35.58% | ETF (Dividend) | Good hold |
| SOFI | US | 15 | $331 | -1.25% | Fintech | Flat, US stock with FX cost |
| SPYM | US | 3.05 | $328 | +25.65% | ETF | Small position |
| SOXL | US | 3.03 | $223 | +70.40% | Leveraged ETF | RISKY — 3x leveraged, not for swing holds |
| ZEQT | TSX | 11.24 | $232 | +11.20% | ETF (All-equity) | Good long-term |
| HXT | TSX | 2 | $173 | +53.40% | ETF (S&P/TSX 60) | Solid |
| CUPR | TSX | 300 | $171 | +18.75% | Commodity (Copper) | Small, momentum play |
| QQC-F | TSX | 0.51 | $95 | +9.15% | ETF (NASDAQ) | Tiny position |
| VISA | US | 2.85 | $79 | +7.57% | Payments | Small + FX cost |

### Immediate Flags the App Should Surface:
1. **NKE: -37% loss across 2 positions.** Review: hold, average down, or cut losses?
2. **UPS: -22% loss.** Downtrend. Review exit strategy.
3. **SOXL: 3x leveraged.** Not suitable for long-term holding. Capture the +70% gain?
4. **US stocks without USD account:** NKE, UPS, SOFI, VISA, SOXL, SPYM all incur 3% FX round-trip.
5. **Portfolio concentration:** VFV is 33% of portfolio. Acceptable for core, but flag it.

---

## 10. Build Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Set up FastAPI backend with PostgreSQL
- [ ] Implement data fetcher service (Twelve Data + Alpha Vantage + Finnhub)
- [ ] Build API response caching layer
- [ ] Create database tables and models
- [ ] Import current holdings into database
- [ ] Build basic portfolio endpoint with live prices
- [ ] Set up Vue 3 project with Vite + PWA config
- [ ] Build Dashboard view (portfolio summary only)

### Phase 2: Analysis Engine (Week 3-4)
- [ ] Implement technical indicator calculations (all 15 indicators)
- [ ] Build scanner engine with all filter criteria
- [ ] Build trade plan generator with position sizing
- [ ] Implement FX cost calculator
- [ ] Implement earnings date checker + blackout rule
- [ ] Build Scanner API endpoints
- [ ] Build Trade Plans API endpoints
- [ ] Build Scanner view in frontend
- [ ] Build Trade Plan detail view in frontend

### Phase 3: Market Intelligence (Week 5-6)
- [ ] Implement BoC Valet API integration
- [ ] Implement commodity price tracking
- [ ] Build sector rotation tracker
- [ ] Build relative strength calculator (stock vs index)
- [ ] Build Market view in frontend (macro + sectors)
- [ ] Build sector heatmap component
- [ ] Add macro context to trade plans

### Phase 4: Notifications & Monitoring (Week 7-8)
- [ ] Set up Telegram bot
- [ ] Implement all alert types
- [ ] Build scheduled jobs (morning scan, price monitor, daily summary)
- [ ] Implement PWA push notifications
- [ ] Build alert feed in frontend
- [ ] Build Settings view (account config, notification preferences)

### Phase 5: Trade Tracking & History (Week 9-10)
- [ ] Build trade execution logging
- [ ] Implement P&L tracking for closed trades
- [ ] Build trade history view with win/loss stats
- [ ] Build portfolio health check (concentration, sector balance)
- [ ] Build risk dashboard (max drawdown, exposure)
- [ ] Polish UI, fix bugs, optimize API calls

### Phase 6: SaaS Prep (Future — Only If You Want)
- [ ] Add authentication (JWT)
- [ ] Multi-user support
- [ ] Stripe billing
- [ ] Custom ticker universe per user
- [ ] Onboarding flow
- [ ] Landing page

---

## 11. Environment Variables (.env)

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/swingdge

# APIs
TWELVE_DATA_KEY=your_key_here
ALPHA_VANTAGE_KEY=your_key_here
FINNHUB_KEY=your_key_here
FMP_KEY=your_key_here
MARKETAUX_KEY=your_key_here

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# App Settings
RISK_PER_TRADE_PCT=1.0
DEFAULT_CURRENCY=CAD
FX_FEE_PCT=1.5
MARKET_OPEN_ET=09:30
MARKET_CLOSE_ET=16:00
EARNINGS_BLACKOUT_DAYS=5
```

---

## 12. Important Rules (Hardcoded in the App)

1. **1% risk per trade.** Never risk more than 1% of account balance on a single trade.
2. **Minimum 2:1 risk/reward.** Never take a trade where the potential gain is less than 2x the potential loss.
3. **Earnings blackout.** No new positions within 5 trading days of earnings.
4. **FX transparency.** Every US stock trade plan shows true cost after 3% FX round-trip.
5. **No penny stocks.** Minimum $2B market cap.
6. **No leveraged ETFs for swing trades.** SOXL and similar are flagged as high-risk.
7. **Max 5 active swing trades at once.** Prevents overtrading.
8. **10-day expiry.** If a trade doesn't hit target or stop within 10 trading days, review for exit.
9. **Sector limit.** Max 30% portfolio in any single sector.
10. **Position limit.** No single position > 15% of portfolio (except broad ETFs like VFV).

---

*⚠️ Disclaimer: This app is a research and tracking tool. It is not financial advice. Always apply your own risk management before placing trades.*
