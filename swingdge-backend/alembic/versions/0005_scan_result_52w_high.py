"""Add high_52w and adx_14 to scan_results

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scan_results", sa.Column("high_52w", sa.Numeric(10, 4), nullable=True))
    op.add_column("scan_results", sa.Column("adx_14", sa.Numeric(6, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("scan_results", "adx_14")
    op.drop_column("scan_results", "high_52w")
