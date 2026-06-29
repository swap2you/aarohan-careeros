"""R2.7 Gmail lifecycle — extended recruiter signal metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0008_r27_gmail_lifecycle"
down_revision = "0007_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recruiter_signals", sa.Column("gmail_message_id", sa.String(128), nullable=True))
    op.add_column("recruiter_signals", sa.Column("gmail_thread_id", sa.String(128), nullable=True))
    op.add_column("recruiter_signals", sa.Column("gmail_label", sa.String(128), nullable=True))
    op.add_column("recruiter_signals", sa.Column("snippet", sa.String(512), nullable=True))
    op.add_column("recruiter_signals", sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=True))
    op.add_column("recruiter_signals", sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True))
    op.add_column("recruiter_signals", sa.Column("classification_confidence", sa.Float(), nullable=True))
    op.add_column("recruiter_signals", sa.Column("user_classification_override", sa.String(64), nullable=True))
    op.add_column("recruiter_signals", sa.Column("follow_up_at", sa.DateTime(), nullable=True))
    op.create_index("ix_recruiter_signals_gmail_message_id", "recruiter_signals", ["gmail_message_id"])
    op.create_index("ix_recruiter_signals_gmail_thread_id", "recruiter_signals", ["gmail_thread_id"])
    op.create_unique_constraint(
        "uq_recruiter_signals_gmail_message",
        "recruiter_signals",
        ["gmail_message_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_recruiter_signals_gmail_message", "recruiter_signals", type_="unique")
    op.drop_index("ix_recruiter_signals_gmail_thread_id", table_name="recruiter_signals")
    op.drop_index("ix_recruiter_signals_gmail_message_id", table_name="recruiter_signals")
    for col in (
        "follow_up_at",
        "user_classification_override",
        "classification_confidence",
        "company_id",
        "application_id",
        "snippet",
        "gmail_label",
        "gmail_thread_id",
        "gmail_message_id",
    ):
        op.drop_column("recruiter_signals", col)
