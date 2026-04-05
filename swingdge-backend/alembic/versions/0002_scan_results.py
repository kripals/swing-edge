"""Add scan_results table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_date", sa.Date(), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("exchange", sa.String(10)),
        sa.Column("current_price", sa.Numeric(10, 4)),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("signal_strength", sa.Numeric(4, 2)),
        sa.Column("rsi_14", sa.Numeric(6, 2)),
        sa.Column("macd_histogram", sa.Numeric(10, 4)),
        sa.Column("volume_ratio", sa.Numeric(6, 2)),
        sa.Column("above_sma_50", sa.Boolean()),
        sa.Column("atr_14", sa.Numeric(10, 4)),
        sa.Column("relative_strength", sa.Numeric(8, 2)),
        sa.Column("sector", sa.String(50)),
        sa.Column("notes", sa.Text()),
        sa.Column("has_trade_plan", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_scan_results_date", "scan_results", ["scan_date"])
    op.create_index("idx_scan_results_ticker", "scan_results", ["ticker"])


def downgrade() -> None:
    op.drop_table("scan_results")
