"""Add portfolio_value_cad to market_snapshots

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_snapshots",
        sa.Column("portfolio_value_cad", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("market_snapshots", "portfolio_value_cad")
