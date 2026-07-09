"""Add Fresh Jobs discovery eligibility and connector run persistence."""

import sqlalchemy as sa
from alembic import op

revision = "0012_fresh_jobs_discovery"
down_revision = "0011_provenance_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("provider_posted_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("source_received_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("effective_freshness_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("freshness_source", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("freshness_bucket", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("location_eligibility", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("location_eligibility_reason", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("role_eligibility", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("role_eligibility_reason", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("recommended_profile", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("profile_scores", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("matched_title_patterns", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("ingest_decision", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("ingest_reason_codes", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("ingest_reasons", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("eligible_for_owner", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("jobs", sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("jobs", sa.Column("canonical_url", sa.String(length=1024), nullable=True))
    op.create_index("ix_jobs_effective_freshness_at", "jobs", ["effective_freshness_at"])
    op.create_index("ix_jobs_location_eligibility", "jobs", ["location_eligibility"])
    op.create_index("ix_jobs_role_eligibility", "jobs", ["role_eligibility"])
    op.create_index("ix_jobs_recommended_profile", "jobs", ["recommended_profile"])
    op.create_index("ix_jobs_ingest_decision", "jobs", ["ingest_decision"])
    op.create_index("ix_jobs_eligible_for_owner", "jobs", ["eligible_for_owner"])
    op.create_index("ix_jobs_is_archived", "jobs", ["is_archived"])
    op.create_index("ix_jobs_canonical_url", "jobs", ["canonical_url"])

    op.create_table(
        "connector_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("search_profile", sa.JSON(), nullable=True),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("secondary_review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quarantined_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("archived_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_redacted", sa.Text(), nullable=True),
        sa.Column("live", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("health_state", sa.String(length=32), nullable=True),
        sa.Column("reason_distribution", sa.JSON(), nullable=True),
        sa.Column("actor", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_connector_runs_provider", "connector_runs", ["provider"])
    op.create_index("ix_connector_runs_started_at", "connector_runs", ["started_at"])
    op.create_index("ix_connector_runs_health_state", "connector_runs", ["health_state"])


def downgrade() -> None:
    op.drop_index("ix_connector_runs_health_state", table_name="connector_runs")
    op.drop_index("ix_connector_runs_started_at", table_name="connector_runs")
    op.drop_index("ix_connector_runs_provider", table_name="connector_runs")
    op.drop_table("connector_runs")
    for idx in (
        "ix_jobs_canonical_url",
        "ix_jobs_is_archived",
        "ix_jobs_eligible_for_owner",
        "ix_jobs_ingest_decision",
        "ix_jobs_recommended_profile",
        "ix_jobs_role_eligibility",
        "ix_jobs_location_eligibility",
        "ix_jobs_effective_freshness_at",
    ):
        op.drop_index(idx, table_name="jobs")
    for col in (
        "canonical_url",
        "is_archived",
        "eligible_for_owner",
        "ingest_reasons",
        "ingest_reason_codes",
        "ingest_decision",
        "matched_title_patterns",
        "profile_scores",
        "recommended_profile",
        "role_eligibility_reason",
        "role_eligibility",
        "location_eligibility_reason",
        "location_eligibility",
        "freshness_bucket",
        "freshness_source",
        "effective_freshness_at",
        "source_received_at",
        "provider_posted_at",
    ):
        op.drop_column("jobs", col)
