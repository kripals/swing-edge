"""
Seed script — run once after migrations to populate:
  1. Default trading rules
  2. Kripal's two TFSA accounts
  3. Full TSX + US ticker universe (50+ tickers)
  4. Kripal's current 14 holdings (with problem flags)

Usage:
    cd swingdge-backend
    python -m scripts.seed
"""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal


# ── Trading Rules ─────────────────────────────────────────────────────────────

TRADING_RULES = [
    # Risk management
    ("risk_per_trade_pct",        "1.0",   "float", "Max % of account to risk on a single trade (1% = disciplined swing trading)", True),
    ("min_risk_reward_ratio",     "2.0",   "float", "Minimum reward:risk ratio to take a trade (2.0 = 2:1)", True),
    ("max_active_trades",         "5",     "int",   "Maximum concurrent open swing trades", True),
    ("trade_expiry_days",         "10",    "int",   "Close or review a trade if it hasn't hit target/stop in this many trading days", True),
    # Position limits
    ("max_position_pct",          "15.0",  "float", "Max % of portfolio in a single position (excl. broad ETFs like VFV)", True),
    ("max_sector_pct",            "30.0",  "float", "Max % of portfolio in a single sector", True),
    # FX
    ("fx_fee_pct",                "1.5",   "float", "Wealthsimple FX fee each way (%) — 1.5% buy + 1.5% sell = 3% round-trip", True),
    ("fx_warning_threshold_pct",  "2.0",   "float", "Show FX WARNING if net gain after FX is below this %", True),
    # Earnings
    ("earnings_blackout_days",    "5",     "int",   "No new trades within this many trading days of an earnings report", False),
    # Scanner filters
    ("scanner_rsi_min",           "30",    "int",   "RSI lower bound for pullback signal", True),
    ("scanner_rsi_max",           "50",    "int",   "RSI upper bound for pullback signal", True),
    ("scanner_volume_ratio_min",  "1.5",   "float", "Minimum volume vs 20-day average to confirm momentum", True),
    ("scanner_min_market_cap_cad","2000000000", "float", "Minimum market cap in CAD to avoid penny/micro caps", False),
    # Trade plan generation
    ("atr_stop_multiplier",       "1.5",   "float", "Stop loss = entry - (ATR * this multiplier)", True),
    ("atr_target1_multiplier",    "3.0",   "float", "Target 1 = entry + (ATR * this multiplier)", True),
    ("atr_target2_multiplier",    "4.5",   "float", "Target 2 = entry + (ATR * this multiplier)", True),
    ("entry_zone_buffer_pct",     "1.0",   "float", "Entry zone upper bound = current_price * (1 + this/100)", True),
]


# ── Ticker Universe ───────────────────────────────────────────────────────────

TICKERS = [
    # (ticker, exchange, name, sector, currency, is_etf, twelve_data_symbol)

    # Energy — TSX
    ("SU.TO",    "TSX", "Suncor Energy",            "Energy",      "CAD", False, "SU:TSX"),
    ("CNQ.TO",   "TSX", "Canadian Natural Resources","Energy",      "CAD", False, "CNQ:TSX"),
    ("CVE.TO",   "TSX", "Cenovus Energy",            "Energy",      "CAD", False, "CVE:TSX"),
    ("ENB.TO",   "TSX", "Enbridge",                  "Energy",      "CAD", False, "ENB:TSX"),
    ("TRP.TO",   "TSX", "TC Energy",                 "Energy",      "CAD", False, "TRP:TSX"),
    ("PPL.TO",   "TSX", "Pembina Pipeline",          "Energy",      "CAD", False, "PPL:TSX"),
    ("IMO.TO",   "TSX", "Imperial Oil",              "Energy",      "CAD", False, "IMO:TSX"),
    ("MEG.TO",   "TSX", "MEG Energy",                "Energy",      "CAD", False, "MEG:TSX"),
    ("WCP.TO",   "TSX", "Whitecap Resources",        "Energy",      "CAD", False, "WCP:TSX"),
    ("ARX.TO",   "TSX", "ARC Resources",             "Energy",      "CAD", False, "ARX:TSX"),

    # Banks & Financials — TSX
    ("RY.TO",    "TSX", "Royal Bank of Canada",      "Financials",  "CAD", False, "RY:TSX"),
    ("TD.TO",    "TSX", "TD Bank",                   "Financials",  "CAD", False, "TD:TSX"),
    ("BNS.TO",   "TSX", "Bank of Nova Scotia",       "Financials",  "CAD", False, "BNS:TSX"),
    ("BMO.TO",   "TSX", "Bank of Montreal",          "Financials",  "CAD", False, "BMO:TSX"),
    ("CM.TO",    "TSX", "CIBC",                      "Financials",  "CAD", False, "CM:TSX"),
    ("NA.TO",    "TSX", "National Bank",             "Financials",  "CAD", False, "NA:TSX"),
    ("MFC.TO",   "TSX", "Manulife Financial",        "Financials",  "CAD", False, "MFC:TSX"),
    ("SLF.TO",   "TSX", "Sun Life Financial",        "Financials",  "CAD", False, "SLF:TSX"),
    ("GWO.TO",   "TSX", "Great-West Lifeco",         "Financials",  "CAD", False, "GWO:TSX"),
    ("POW.TO",   "TSX", "Power Corporation",         "Financials",  "CAD", False, "POW:TSX"),
    ("IFC.TO",   "TSX", "Intact Financial",          "Financials",  "CAD", False, "IFC:TSX"),

    # Mining & Materials — TSX
    ("ABX.TO",   "TSX", "Barrick Gold",              "Materials",   "CAD", False, "ABX:TSX"),
    ("AEM.TO",   "TSX", "Agnico Eagle Mines",        "Materials",   "CAD", False, "AEM:TSX"),
    ("NTR.TO",   "TSX", "Nutrien",                   "Materials",   "CAD", False, "NTR:TSX"),
    ("FM.TO",    "TSX", "First Quantum Minerals",    "Materials",   "CAD", False, "FM:TSX"),
    ("TECK.TO",  "TSX", "Teck Resources",            "Materials",   "CAD", False, "TECK:TSX"),
    ("FNV.TO",   "TSX", "Franco-Nevada",             "Materials",   "CAD", False, "FNV:TSX"),
    ("WPM.TO",   "TSX", "Wheaton Precious Metals",   "Materials",   "CAD", False, "WPM:TSX"),
    ("K.TO",     "TSX", "Kinross Gold",              "Materials",   "CAD", False, "K:TSX"),
    ("LUN.TO",   "TSX", "Lundin Mining",             "Materials",   "CAD", False, "LUN:TSX"),

    # Industrials & Transport — TSX
    ("CP.TO",    "TSX", "Canadian Pacific Kansas City","Industrials","CAD", False, "CP:TSX"),
    ("CNR.TO",   "TSX", "Canadian National Railway", "Industrials", "CAD", False, "CNR:TSX"),
    ("WFG.TO",   "TSX", "West Fraser Timber",        "Industrials", "CAD", False, "WFG:TSX"),
    ("TIH.TO",   "TSX", "Toromont Industries",       "Industrials", "CAD", False, "TIH:TSX"),
    ("SJ.TO",    "TSX", "Stella-Jones",              "Industrials", "CAD", False, "SJ:TSX"),
    ("CAE.TO",   "TSX", "CAE Inc",                   "Industrials", "CAD", False, "CAE:TSX"),
    ("WSP.TO",   "TSX", "WSP Global",                "Industrials", "CAD", False, "WSP:TSX"),

    # Tech & Telecom — TSX
    ("SHOP.TO",  "TSX", "Shopify",                   "Technology",  "CAD", False, "SHOP:TSX"),
    ("CSU.TO",   "TSX", "Constellation Software",    "Technology",  "CAD", False, "CSU:TSX"),
    ("OTEX.TO",  "TSX", "Open Text",                 "Technology",  "CAD", False, "OTEX:TSX"),
    ("T.TO",     "TSX", "TELUS",                     "Telecom",     "CAD", False, "T:TSX"),
    ("BCE.TO",   "TSX", "BCE Inc",                   "Telecom",     "CAD", False, "BCE:TSX"),
    ("RCI-B.TO", "TSX", "Rogers Communications",     "Telecom",     "CAD", False, "RCI.B:TSX"),

    # Real Estate & Utilities — TSX
    ("BAM.TO",   "TSX", "Brookfield Asset Management","Real Estate","CAD", False, "BAM:TSX"),
    ("BN.TO",    "TSX", "Brookfield Corporation",    "Real Estate", "CAD", False, "BN:TSX"),
    ("FTS.TO",   "TSX", "Fortis",                    "Utilities",   "CAD", False, "FTS:TSX"),
    ("EMA.TO",   "TSX", "Emera",                     "Utilities",   "CAD", False, "EMA:TSX"),
    ("AQN.TO",   "TSX", "Algonquin Power",           "Utilities",   "CAD", False, "AQN:TSX"),
    ("REI-UN.TO","TSX", "RioCan REIT",               "Real Estate", "CAD", False, "REI.UN:TSX"),
    ("CAR-UN.TO","TSX", "Canadian Apartment REIT",   "Real Estate", "CAD", False, "CAR.UN:TSX"),

    # TSX ETFs (sector rotation tracking)
    ("XIU.TO",   "TSX", "iShares S&P/TSX 60",        "ETF",         "CAD", True,  "XIU:TSX"),
    ("XIC.TO",   "TSX", "iShares Core S&P/TSX Capped","ETF",        "CAD", True,  "XIC:TSX"),
    ("XEI.TO",   "TSX", "iShares S&P/TSX Composite High Div","ETF", "CAD", True,  "XEI:TSX"),
    ("VFV.TO",   "TSX", "Vanguard S&P 500 Index (CAD)","ETF",       "CAD", True,  "VFV:TSX"),
    ("VDY.TO",   "TSX", "Vanguard FTSE Canadian High Div","ETF",    "CAD", True,  "VDY:TSX"),
    ("ZEB.TO",   "TSX", "BMO Equal Weight Banks",    "ETF",         "CAD", True,  "ZEB:TSX"),
    ("XEG.TO",   "TSX", "iShares S&P/TSX Capped Energy","ETF",      "CAD", True,  "XEG:TSX"),
    ("XGD.TO",   "TSX", "iShares S&P/TSX Global Gold","ETF",        "CAD", True,  "XGD:TSX"),
    ("XMA.TO",   "TSX", "iShares S&P/TSX Capped Materials","ETF",   "CAD", True,  "XMA:TSX"),
    ("ZSP.TO",   "TSX", "BMO S&P 500 Index",         "ETF",         "CAD", True,  "ZSP:TSX"),
    ("ZEQT.TO",  "TSX", "BMO All-Equity ETF",         "ETF",        "CAD", True,  "ZEQT:TSX"),
    ("HXT.TO",   "TSX", "Horizons S&P/TSX 60",       "ETF",         "CAD", True,  "HXT:TSX"),
    ("QQC-F.TO", "TSX", "Invesco NASDAQ 100 (CAD-hedged)","ETF",    "CAD", True,  "QQC.F:TSX"),
    ("CUPR.TO",  "TSX", "Horizons Copper ETF",        "ETF",        "CAD", True,  "CUPR:TSX"),

    # US Stocks
    ("NKE",      "NYSE",   "Nike",                   "Consumer",    "USD", False, "NKE"),
    ("UPS",      "NYSE",   "United Parcel Service",  "Industrials", "USD", False, "UPS"),
    ("SOFI",     "NASDAQ", "SoFi Technologies",      "Fintech",     "USD", False, "SOFI"),
    ("VISA",     "NYSE",   "Visa",                   "Financials",  "USD", False, "V"),

    # US ETFs held by Kripal
    ("SPYM",     "NYSE",   "SPDR Portfolio S&P 500 (Mid-Cap)","ETF","USD", True,  "SPYM"),
    ("SOXL",     "NYSE",   "Direxion Daily Semicon 3x Bull","ETF",  "USD", True,  "SOXL"),
]


# ── Accounts ──────────────────────────────────────────────────────────────────

ACCOUNTS = [
    {
        "name": "Kripal TFSA",
        "broker": "wealthsimple",
        "account_type": "TFSA",
        "currency": "CAD",
        "has_usd_account": False,
        "balance": 5287.00,
        "contribution_room": None,
    },
    {
        "name": "Sushma TFSA",
        "broker": "wealthsimple",
        "account_type": "TFSA",
        "currency": "CAD",
        "has_usd_account": False,
        "balance": 2000.00,
        "contribution_room": None,
    },
]


# ── Current Holdings (as of April 2026) ──────────────────────────────────────
# account_name, ticker, exchange, shares, avg_cost, currency, sector, is_leveraged_etf, notes

HOLDINGS = [
    # account_name, ticker, exchange, shares, avg_cost, currency, sector, is_leveraged_etf
    ("Kripal TFSA", "VFV.TO",   "TSX",    14.97, 141.00, "CAD", "ETF",         False),
    ("Kripal TFSA", "XEI.TO",   "TSX",    20.28,  27.50, "CAD", "ETF",         False),
    ("Kripal TFSA", "ENB.TO",   "TSX",     8.33,  51.00, "CAD", "Energy",      False),
    ("Kripal TFSA", "NKE",      "NYSE",   46.89,  41.55, "USD", "Consumer",    False),  # PROBLEM: -37%
    ("Kripal TFSA", "UPS",      "NYSE",    3.25, 170.00, "USD", "Industrials", False),  # PROBLEM: -22%
    ("Kripal TFSA", "VDY.TO",   "TSX",     7.33,  48.10, "CAD", "ETF",         False),
    ("Kripal TFSA", "SOFI",     "NASDAQ", 15.00,  10.90, "USD", "Fintech",     False),
    ("Kripal TFSA", "SPYM",     "NYSE",    3.05,  85.00, "USD", "ETF",         False),
    ("Kripal TFSA", "SOXL",     "NYSE",    3.03,  21.90, "USD", "ETF",         True),   # RISK: 3x leveraged
    ("Kripal TFSA", "ZEQT.TO",  "TSX",    11.24,  18.50, "CAD", "ETF",         False),
    ("Kripal TFSA", "HXT.TO",   "TSX",     2.00,  71.00, "CAD", "ETF",         False),
    ("Kripal TFSA", "CUPR.TO",  "TSX",   300.00,   0.48, "CAD", "Materials",   False),
    ("Kripal TFSA", "QQC-F.TO", "TSX",     0.51, 148.00, "CAD", "ETF",         False),
    ("Kripal TFSA", "VISA",     "NYSE",    2.85, 270.00, "USD", "Financials",  False),
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # 1. Trading rules
        print("Seeding trading rules...")
        for key, value, vtype, desc, editable in TRADING_RULES:
            await session.execute(
                text("""
                    INSERT INTO trading_rules (rule_key, rule_value, value_type, description, is_editable)
                    VALUES (:key, :value, :vtype, :desc, :editable)
                    ON CONFLICT (rule_key) DO UPDATE
                        SET rule_value = EXCLUDED.rule_value,
                            description = EXCLUDED.description
                """),
                {"key": key, "value": value, "vtype": vtype, "desc": desc, "editable": editable},
            )

        # 2. Ticker universe
        print("Seeding ticker universe...")
        for row in TICKERS:
            ticker, exchange, name, sector, currency, is_etf, td_symbol = row
            await session.execute(
                text("""
                    INSERT INTO ticker_universe (ticker, exchange, name, sector, currency, is_etf, twelve_data_symbol)
                    VALUES (:ticker, :exchange, :name, :sector, :currency, :is_etf, :td_symbol)
                    ON CONFLICT (ticker) DO UPDATE
                        SET name = EXCLUDED.name,
                            sector = EXCLUDED.sector,
                            twelve_data_symbol = EXCLUDED.twelve_data_symbol
                """),
                {"ticker": ticker, "exchange": exchange, "name": name, "sector": sector,
                 "currency": currency, "is_etf": is_etf, "td_symbol": td_symbol},
            )

        # 3. Accounts
        print("Seeding accounts...")
        account_ids: dict[str, int] = {}
        for acc in ACCOUNTS:
            result = await session.execute(
                text("""
                    INSERT INTO accounts (name, broker, account_type, currency, has_usd_account, balance)
                    VALUES (:name, :broker, :account_type, :currency, :has_usd_account, :balance)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """),
                acc,
            )
            row = result.fetchone()
            if row:
                account_ids[acc["name"]] = row[0]
            else:
                # Already exists — fetch the id
                r = await session.execute(
                    text("SELECT id FROM accounts WHERE name = :name"),
                    {"name": acc["name"]},
                )
                account_ids[acc["name"]] = r.scalar_one()

        # 4. Holdings
        print("Seeding current holdings...")
        for acc_name, ticker, exchange, shares, avg_cost, currency, sector, is_lev in HOLDINGS:
            account_id = account_ids.get(acc_name)
            if not account_id:
                print(f"  Warning: account '{acc_name}' not found, skipping {ticker}")
                continue
            has_fx = currency == "USD"
            await session.execute(
                text("""
                    INSERT INTO holdings (account_id, ticker, exchange, shares, avg_cost, currency, sector, is_leveraged_etf, has_fx_cost)
                    VALUES (:account_id, :ticker, :exchange, :shares, :avg_cost, :currency, :sector, :is_lev, :has_fx)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "account_id": account_id, "ticker": ticker, "exchange": exchange,
                    "shares": shares, "avg_cost": avg_cost, "currency": currency,
                    "sector": sector, "is_lev": is_lev, "has_fx": has_fx,
                },
            )

        await session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
