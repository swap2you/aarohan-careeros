"""Application ledger and duplicate protection.

Revision ID: 0004_duplicate_protection
Revises: 0003_fk_not_null
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_duplicate_protection"
down_revision = "0003_fk_not_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("parent_company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_normalized_name", "companies", ["normalized_name"], unique=True)

    op.create_table(
        "company_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("normalized_alias", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_aliases_normalized_alias", "company_aliases", ["normalized_alias"])

    op.create_table(
        "company_domains",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_domains_domain", "company_domains", ["domain"], unique=True)

    op.create_table(
        "company_ats_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("ats_type", sa.String(64), nullable=False),
        sa.Column("board_token", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ats_type", "board_token", name="uq_ats_type_board"),
    )

    op.create_table(
        "application_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("requisition_id", sa.String(255), nullable=True),
        sa.Column("ats_job_id", sa.String(255), nullable=True),
        sa.Column("application_url", sa.String(1024), nullable=True),
        sa.Column("normalized_title", sa.String(512), nullable=True),
        sa.Column("description_fingerprint", sa.String(128), nullable=True),
        sa.Column("vendor_channel", sa.String(255), nullable=True),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_ledger_company_id", "application_ledger", ["company_id"])
    op.create_index("ix_application_ledger_requisition_id", "application_ledger", ["requisition_id"])
    op.create_index("ix_application_ledger_ats_job_id", "application_ledger", ["ats_job_id"])
    op.create_index("ix_application_ledger_application_url", "application_ledger", ["application_url"])

    op.create_table(
        "application_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("application_ledger.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_email", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_events_ledger_id", "application_events", ["ledger_id"])

    op.create_table(
        "duplicate_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("application_ledger.id"), nullable=True),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_email", sa.String(255), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("matched_records", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_duplicate_overrides_job_id", "duplicate_overrides", ["job_id"])

    op.add_column("jobs", sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True))
    op.add_column("jobs", sa.Column("requisition_id", sa.String(255), nullable=True))
    op.add_column("jobs", sa.Column("ats_job_id", sa.String(255), nullable=True))
    op.add_column("jobs", sa.Column("description_fingerprint", sa.String(128), nullable=True))
    op.add_column("jobs", sa.Column("normalized_title", sa.String(512), nullable=True))
    op.create_index("ix_jobs_company_id", "jobs", ["company_id"])
    op.create_index("ix_jobs_requisition_id", "jobs", ["requisition_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_requisition_id", table_name="jobs")
    op.drop_index("ix_jobs_company_id", table_name="jobs")
    op.drop_column("jobs", "normalized_title")
    op.drop_column("jobs", "description_fingerprint")
    op.drop_column("jobs", "ats_job_id")
    op.drop_column("jobs", "requisition_id")
    op.drop_column("jobs", "company_id")
    op.drop_table("duplicate_overrides")
    op.drop_table("application_events")
    op.drop_table("application_ledger")
    op.drop_table("company_ats_identities")
    op.drop_table("company_domains")
    op.drop_table("company_aliases")
    op.drop_table("companies")
