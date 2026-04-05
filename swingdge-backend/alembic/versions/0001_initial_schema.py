"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── accounts ─────────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("broker", sa.String(50), server_default="wealthsimple"),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), server_default="CAD"),
        sa.Column("has_usd_account", sa.Boolean, server_default="false"),
        sa.Column("balance", sa.Numeric(12, 2)),
        sa.Column("contribution_room", sa.Numeric(12, 2)),
        sa.Column("snaptrade_account_id", sa.String(100)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── holdings ─────────────────────────────────────────────────────────────
    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("shares", sa.Numeric(10, 4), nullable=False),
        sa.Column("avg_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("current_price", sa.Numeric(10, 4)),
        sa.Column("unrealized_pnl", sa.Numeric(10, 2)),
        sa.Column("unrealized_pnl_pct", sa.Numeric(6, 2)),
        sa.Column("sector", sa.String(50)),
        sa.Column("is_leveraged_etf", sa.Boolean, server_default="false"),
        sa.Column("has_fx_cost", sa.Boolean, server_default="false"),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_holdings_account", "holdings", ["account_id"])
    op.create_index("idx_holdings_ticker", "holdings", ["ticker"])

    # ── watchlist ─────────────────────────────────────────────────────────────
    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("sector", sa.String(50)),
        sa.Column("added_reason", sa.Text),
        sa.Column("status", sa.String(20), server_default="watching"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    # ── trade_plans ───────────────────────────────────────────────────────────
    op.create_table(
        "trade_plans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("sector", sa.String(50)),
        sa.Column("current_price", sa.Numeric(10, 4), nullable=False),
        sa.Column("entry_low", sa.Numeric(10, 4), nullable=False),
        sa.Column("entry_high", sa.Numeric(10, 4), nullable=False),
        sa.Column("stop_loss", sa.Numeric(10, 4), nullable=False),
        sa.Column("target_1", sa.Numeric(10, 4), nullable=False),
        sa.Column("target_2", sa.Numeric(10, 4), nullable=False),
        sa.Column("risk_reward_ratio", sa.Numeric(4, 2), nullable=False),
        sa.Column("position_size_dollars", sa.Numeric(10, 2), nullable=False),
        sa.Column("position_size_shares", sa.Numeric(10, 4), nullable=False),
        sa.Column("risk_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("fx_cost_pct", sa.Numeric(4, 2), server_default="0.00"),
        sa.Column("net_gain_after_fx", sa.Numeric(6, 2)),
        sa.Column("earnings_date", sa.Date),
        sa.Column("earnings_days_away", sa.Integer),
        sa.Column("signal_type", sa.String(50)),
        sa.Column("signal_score", sa.Numeric(4, 2)),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_price", sa.Numeric(10, 4)),
        sa.Column("actual_pnl", sa.Numeric(10, 2)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_trade_plans_ticker", "trade_plans", ["ticker"])
    op.create_index("idx_trade_plans_status", "trade_plans", ["status"])

    # ── trade_history ─────────────────────────────────────────────────────────
    op.create_table(
        "trade_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("trade_plan_id", sa.Integer, sa.ForeignKey("trade_plans.id")),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("entry_price", sa.Numeric(10, 4), nullable=False),
        sa.Column("exit_price", sa.Numeric(10, 4), nullable=False),
        sa.Column("shares", sa.Numeric(10, 4), nullable=False),
        sa.Column("gross_pnl", sa.Numeric(10, 2), nullable=False),
        sa.Column("fx_cost", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("net_pnl", sa.Numeric(10, 2), nullable=False),
        sa.Column("hold_days", sa.Integer),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("signal_type", sa.String(50)),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_trade_history_ticker", "trade_history", ["ticker"])
    op.create_index("idx_trade_history_account", "trade_history", ["account_id"])

    # ── market_snapshots ──────────────────────────────────────────────────────
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False, unique=True),
        sa.Column("tsx_composite", sa.Numeric(10, 2)),
        sa.Column("sp500", sa.Numeric(10, 2)),
        sa.Column("usd_cad", sa.Numeric(8, 4)),
        sa.Column("boc_rate", sa.Numeric(4, 2)),
        sa.Column("wti_oil", sa.Numeric(8, 2)),
        sa.Column("gold", sa.Numeric(10, 2)),
        sa.Column("nat_gas", sa.Numeric(8, 4)),
        sa.Column("copper", sa.Numeric(8, 4)),
        sa.Column("cpi", sa.Numeric(4, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_market_snapshots_date", "market_snapshots", ["date"])

    # ── sector_performance ────────────────────────────────────────────────────
    op.create_table(
        "sector_performance",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("sector", sa.String(50), nullable=False),
        sa.Column("etf_ticker", sa.String(20), nullable=False),
        sa.Column("performance_1d", sa.Numeric(6, 2)),
        sa.Column("performance_5d", sa.Numeric(6, 2)),
        sa.Column("performance_20d", sa.Numeric(6, 2)),
        sa.Column("relative_strength", sa.Numeric(6, 2)),
        sa.Column("volume_ratio", sa.Numeric(6, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_sector_perf_date", "sector_performance", ["date"])

    # ── alerts ────────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("ticker", sa.String(20)),
        sa.Column("priority", sa.String(10), server_default="medium"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("sent_via", sa.String(20)),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("acknowledged", sa.Boolean, server_default="false"),
    )
    op.create_index("idx_alerts_sent_at", "alerts", ["sent_at"])

    # ── api_cache ─────────────────────────────────────────────────────────────
    op.create_table(
        "api_cache",
        sa.Column("cache_key", sa.String(200), primary_key=True),
        sa.Column("cache_value", postgresql.JSONB, nullable=False),
        sa.Column("provider", sa.String(50)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_api_cache_expires", "api_cache", ["expires_at"])

    # ── trading_rules ─────────────────────────────────────────────────────────
    op.create_table(
        "trading_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("rule_key", sa.String(100), nullable=False, unique=True),
        sa.Column("rule_value", sa.String(200), nullable=False),
        sa.Column("value_type", sa.String(20), server_default="float"),
        sa.Column("description", sa.Text),
        sa.Column("is_editable", sa.Boolean, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── ticker_universe ───────────────────────────────────────────────────────
    op.create_table(
        "ticker_universe",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False, unique=True),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("sector", sa.String(50)),
        sa.Column("currency", sa.String(3), server_default="CAD"),
        sa.Column("is_etf", sa.Boolean, server_default="false"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("twelve_data_symbol", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ticker_universe")
    op.drop_table("trading_rules")
    op.drop_table("api_cache")
    op.drop_table("alerts")
    op.drop_table("sector_performance")
    op.drop_table("market_snapshots")
    op.drop_table("trade_history")
    op.drop_table("trade_plans")
    op.drop_table("watchlist")
    op.drop_table("holdings")
    op.drop_table("accounts")
