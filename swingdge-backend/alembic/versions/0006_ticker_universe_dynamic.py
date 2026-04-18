"""Add expires_at and discovery_source to ticker_universe

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ticker_universe",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ticker_universe",
        sa.Column(
            "discovery_source",
            sa.String(30),
            nullable=True,
            comment="'manual' | 'fmp_screener' | 'momentum'",
        ),
    )


def downgrade() -> None:
    op.drop_column("ticker_universe", "expires_at")
    op.drop_column("ticker_universe", "discovery_source")
