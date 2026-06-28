"""R2.5 manual workflow: representation, document versions, timeline."""

from alembic import op
import sqlalchemy as sa

revision = "0006_r25_manual_workflow"
down_revision = "0005_trust_matching"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("application_ledger", sa.Column("source", sa.String(64), nullable=True))
    op.add_column("application_ledger", sa.Column("external_id", sa.String(255), nullable=True))
    op.create_index("ix_application_ledger_source", "application_ledger", ["source"])
    op.create_index("ix_application_ledger_external_id", "application_ledger", ["external_id"])

    op.create_table(
        "application_document_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("docx_path", sa.String(1024), nullable=False),
        sa.Column("pdf_path", sa.String(1024), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("drive_docx_id", sa.String(255), nullable=True),
        sa.Column("drive_pdf_id", sa.String(255), nullable=True),
        sa.Column("job_snapshot", sa.JSON(), nullable=True),
        sa.Column("template_version", sa.String(32), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("model_version", sa.String(32), nullable=True),
        sa.Column("factual_core_hash", sa.String(128), nullable=True),
        sa.Column("approval_details", sa.JSON(), nullable=True),
        sa.Column("is_submitted_immutable", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("application_id", "version_number", name="uq_app_doc_version"),
    )

    op.add_column("applications", sa.Column("submitted_version_id", sa.Integer(), nullable=True))
    op.add_column(
        "applications",
        sa.Column("latest_version_number", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_foreign_key(
        "fk_applications_submitted_version",
        "applications",
        "application_document_versions",
        ["submitted_version_id"],
        ["id"],
    )

    op.create_table(
        "representation_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vendor_name", sa.String(255), nullable=False, index=True),
        sa.Column("client_company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True, index=True),
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("normalized_client", sa.String(255), nullable=False, index=True),
        sa.Column("requisition_id", sa.String(255), nullable=True, index=True),
        sa.Column("role_title", sa.String(512), nullable=True),
        sa.Column("submission_date", sa.DateTime(), nullable=True),
        sa.Column("representation_start", sa.DateTime(), nullable=True),
        sa.Column("representation_end", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active", index=True),
        sa.Column("recruiter_contact", sa.String(255), nullable=True),
        sa.Column("source_evidence", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("no_agreement_confirmed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "representation_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("representation_id", sa.Integer(), sa.ForeignKey("representation_records.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "application_timeline_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True, index=True),
        sa.Column("event_type", sa.String(64), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("application_timeline_events")
    op.drop_table("representation_overrides")
    op.drop_table("representation_records")
    op.drop_constraint("fk_applications_submitted_version", "applications", type_="foreignkey")
    op.drop_column("applications", "latest_version_number")
    op.drop_column("applications", "submitted_version_id")
    op.drop_table("application_document_versions")
    op.drop_index("ix_application_ledger_external_id", "application_ledger")
    op.drop_index("ix_application_ledger_source", "application_ledger")
    op.drop_column("application_ledger", "external_id")
    op.drop_column("application_ledger", "source")
