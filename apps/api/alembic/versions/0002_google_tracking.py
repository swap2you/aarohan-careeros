"""Revision ID: 0002_google_tracking
Revises: 0001_initial
Create Date: 2026-06-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_google_tracking"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_gmail_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index("ix_processed_gmail_messages_message_id", "processed_gmail_messages", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_processed_gmail_messages_message_id", table_name="processed_gmail_messages")
    op.drop_table("processed_gmail_messages")
