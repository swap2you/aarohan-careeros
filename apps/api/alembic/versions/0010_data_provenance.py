"""Add data provenance and Gmail ingest review quarantine."""

from alembic import op
import sqlalchemy as sa

revision = "0010_data_provenance"
down_revision = "0009_r28_interview_intel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("data_provenance", sa.String(length=32), server_default="live", nullable=False),
    )
    op.create_index("ix_jobs_data_provenance", "jobs", ["data_provenance"])

    op.add_column(
        "companies",
        sa.Column("data_provenance", sa.String(length=32), server_default="live", nullable=False),
    )
    op.create_index("ix_companies_data_provenance", "companies", ["data_provenance"])

    op.add_column(
        "applications",
        sa.Column("data_provenance", sa.String(length=32), server_default="live", nullable=False),
    )

    op.execute(
        """
        UPDATE jobs SET data_provenance = 'fixture'
        WHERE lower(source) LIKE '%fixture%' OR lower(source) IN ('test', 'e2e')
        """
    )
    op.execute(
        """
        UPDATE jobs SET data_provenance = 'gmail'
        WHERE lower(source) LIKE 'gmail%'
        """
    )
    op.execute(
        """
        UPDATE jobs SET data_provenance = 'connector'
        WHERE lower(source) IN (
            'greenhouse','lever','ashby','remotive','remoteok',
            'adzuna','jooble','usajobs','rss','public_feed'
        )
        """
    )

    op.create_table(
        "gmail_ingest_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=True, index=True),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=True),
        sa.Column("gmail_label", sa.String(length=255), nullable=True),
        sa.Column("sender", sa.String(length=512), nullable=True),
        sa.Column("subject", sa.String(length=1024), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="quarantined", nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("ignored_reason", sa.Text(), nullable=True),
        sa.Column("parsed_payload", sa.JSON(), nullable=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("recruiter_signal_id", sa.Integer(), sa.ForeignKey("recruiter_signals.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gmail_ingest_reviews")
    op.drop_column("applications", "data_provenance")
    op.drop_index("ix_companies_data_provenance", table_name="companies")
    op.drop_column("companies", "data_provenance")
    op.drop_index("ix_jobs_data_provenance", table_name="jobs")
    op.drop_column("jobs", "data_provenance")
