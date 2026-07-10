"""Add durable Gmail replay state to processed_gmail_messages."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014_gmail_replay_state"
down_revision = "0013_database_identity_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "processed_gmail_messages",
        sa.Column("message_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "processed_gmail_messages",
        sa.Column("parser_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "processed_gmail_messages",
        sa.Column("processing_status", sa.String(length=32), server_default="LEGACY", nullable=False),
    )
    op.add_column(
        "processed_gmail_messages",
        sa.Column("produced_entity_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "processed_gmail_messages",
        sa.Column("produced_entity_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "processed_gmail_messages",
        sa.Column("produced_entity_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "processed_gmail_messages",
        sa.Column("last_processing_result", sa.Text(), nullable=True),
    )
    op.add_column(
        "processed_gmail_messages",
        sa.Column("replay_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "processed_gmail_messages",
        sa.Column("replay_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "processed_gmail_messages",
        sa.Column("last_attempted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_processed_gmail_messages_replay_required",
        "processed_gmail_messages",
        ["replay_required"],
    )


def downgrade() -> None:
    op.drop_index("ix_processed_gmail_messages_replay_required", table_name="processed_gmail_messages")
    op.drop_column("processed_gmail_messages", "last_attempted_at")
    op.drop_column("processed_gmail_messages", "replay_reason")
    op.drop_column("processed_gmail_messages", "replay_required")
    op.drop_column("processed_gmail_messages", "last_processing_result")
    op.drop_column("processed_gmail_messages", "produced_entity_count")
    op.drop_column("processed_gmail_messages", "produced_entity_id")
    op.drop_column("processed_gmail_messages", "produced_entity_type")
    op.drop_column("processed_gmail_messages", "processing_status")
    op.drop_column("processed_gmail_messages", "parser_version")
    op.drop_column("processed_gmail_messages", "message_type")
