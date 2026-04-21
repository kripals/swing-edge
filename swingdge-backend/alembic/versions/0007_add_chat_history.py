"""Add chat_history table

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("ai_reply", sa.Text(), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=True),
        sa.Column("context_used", sa.String(20), nullable=False, server_default="general"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("chat_history")
