"""Add unique constraint on holdings(account_id, ticker)

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-06
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_holdings_account_ticker",
        "holdings",
        ["account_id", "ticker"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_holdings_account_ticker", "holdings", type_="unique")
