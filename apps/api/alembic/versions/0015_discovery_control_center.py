"""Workflow 01.5 — Discovery Control Center.

Adds the versioned owner discovery-policy table and job origin / manual-opportunity columns.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015_discovery_control_center"
down_revision = "0014_gmail_replay_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_policy_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("preset", sa.String(length=16), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("overrides", sa.JSON(), nullable=True),
        sa.Column("defaults_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("activated_by", sa.String(length=255), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_discovery_policy_versions_version", "discovery_policy_versions", ["version"]
    )
    op.create_index(
        "ix_discovery_policy_versions_status", "discovery_policy_versions", ["status"]
    )

    op.add_column("jobs", sa.Column("origin", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("origin_detail", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("added_by", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("added_at", sa.DateTime(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("owner_confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("manual_protected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("jobs", sa.Column("manual_status", sa.String(length=32), nullable=True))
    op.create_index("ix_jobs_origin", "jobs", ["origin"])
    op.create_index("ix_jobs_manual_protected", "jobs", ["manual_protected"])
    op.create_index("ix_jobs_manual_status", "jobs", ["manual_status"])

    # Deterministic origin backfill from existing provenance/source (no owner data change).
    op.execute(
        """
        UPDATE jobs SET origin = CASE
            WHEN data_provenance = 'manual' THEN 'OWNER_ADDED'
            WHEN data_provenance = 'gmail' THEN 'GMAIL_ALERT'
            WHEN source IN ('greenhouse', 'lever', 'ashby') THEN 'ATS_BOARD'
            ELSE 'PUBLIC_CONNECTOR'
        END
        WHERE origin IS NULL
        """
    )
    # Owner-added rows are protected from automated age-out once created.
    op.execute(
        "UPDATE jobs SET manual_protected = true WHERE origin = 'OWNER_ADDED'"
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_manual_status", table_name="jobs")
    op.drop_index("ix_jobs_manual_protected", table_name="jobs")
    op.drop_index("ix_jobs_origin", table_name="jobs")
    op.drop_column("jobs", "manual_status")
    op.drop_column("jobs", "manual_protected")
    op.drop_column("jobs", "owner_confirmed")
    op.drop_column("jobs", "added_at")
    op.drop_column("jobs", "added_by")
    op.drop_column("jobs", "origin_detail")
    op.drop_column("jobs", "origin")
    op.drop_index("ix_discovery_policy_versions_status", table_name="discovery_policy_versions")
    op.drop_index("ix_discovery_policy_versions_version", table_name="discovery_policy_versions")
    op.drop_table("discovery_policy_versions")
