"""complete schema

Revision ID: 0001
Revises:
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)

    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("service", sa.String(64), nullable=False),
        sa.Column("account_email", sa.String(255), nullable=True),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("scopes", sa.String(512), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_oauth_tokens_provider", "oauth_tokens", ["provider"])
    op.create_index("ix_oauth_tokens_service", "oauth_tokens", ["service"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("workplace_type", sa.String(64), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("description_html", sa.Text(), nullable=False),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
        sa.Column("freshness_hours", sa.Float(), nullable=True),
        sa.Column("dedupe_key", sa.String(512), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.UniqueConstraint("source", "external_id", name="uq_job_source_external"),
    )
    op.create_index("ix_jobs_source", "jobs", ["source"])
    op.create_index("ix_jobs_company", "jobs", ["company"])
    op.create_index("ix_jobs_dedupe_key", "jobs", ["dedupe_key"])
    op.create_index("ix_jobs_state", "jobs", ["state"])

    op.create_table(
        "job_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), unique=True),
        sa.Column("total_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("compensation_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("remote_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("technical_fit_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("leadership_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ai_alignment_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stability_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fit_analysis", sa.Text(), nullable=True),
        sa.Column("gap_analysis", sa.Text(), nullable=True),
        sa.Column("stability_analysis", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.String(64), nullable=True),
        sa.Column("scored_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_job_scores_total_score", "job_scores", ["total_score"])

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), unique=True),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("resume_docx_path", sa.String(1024), nullable=True),
        sa.Column("resume_pdf_path", sa.String(1024), nullable=True),
        sa.Column("resume_profile", sa.String(128), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("recruiter_note", sa.Text(), nullable=True),
        sa.Column("fit_analysis", sa.Text(), nullable=True),
        sa.Column("packet_metadata", sa.JSON(), nullable=True),
        sa.Column("drive_folder_id", sa.String(255), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_applications_state", "applications", ["state"])

    op.create_table(
        "approval_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_approval_actions_application_id", "approval_actions", ["application_id"])

    op.create_table(
        "recruiter_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("sender", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(512), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("signal_type", sa.String(64), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_recruiter_signals_signal_type", "recruiter_signals", ["signal_type"])

    op.create_table(
        "interview_packs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id")),
        sa.Column("company_briefing", sa.Text(), nullable=True),
        sa.Column("role_map", sa.Text(), nullable=True),
        sa.Column("gap_analysis", sa.Text(), nullable=True),
        sa.Column("questions", sa.JSON(), nullable=True),
        sa.Column("star_stories", sa.JSON(), nullable=True),
        sa.Column("exercises", sa.JSON(), nullable=True),
        sa.Column("weak_areas", sa.JSON(), nullable=True),
        sa.Column("prep_plan", sa.Text(), nullable=True),
        sa.Column("voice_mock_prompt", sa.Text(), nullable=True),
        sa.Column("answer_rubric", sa.JSON(), nullable=True),
        sa.Column("system_design", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_interview_packs_job_id", "interview_packs", ["job_id"])

    op.create_table(
        "consulting_leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("problem_summary", sa.Text(), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("recommended_service", sa.String(255), nullable=True),
        sa.Column("proposal_draft", sa.Text(), nullable=True),
        sa.Column("lead_score", sa.Float(), nullable=True),
        sa.Column("case_study_mapping", sa.JSON(), nullable=True),
        sa.Column("follow_up_status", sa.String(64), nullable=True),
        sa.Column("follow_up_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_consulting_leads_company", "consulting_leads", ["company"])
    op.create_index("ix_consulting_leads_state", "consulting_leads", ["state"])

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evidence_id", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("public_use", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verification_needed", sa.JSON(), nullable=True),
    )
    op.create_index("ix_evidence_items_evidence_id", "evidence_items", ["evidence_id"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "ai_usage_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation", sa.String(128), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_usage_records_operation", "ai_usage_records", ["operation"])
    op.create_index("ix_ai_usage_records_created_at", "ai_usage_records", ["created_at"])

    op.create_table(
        "validation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_validation_runs_status", "validation_runs", ["status"])
    op.create_index("ix_validation_runs_created_at", "validation_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("validation_runs")
    op.drop_table("ai_usage_records")
    op.drop_table("audit_logs")
    op.drop_table("evidence_items")
    op.drop_table("consulting_leads")
    op.drop_table("interview_packs")
    op.drop_table("recruiter_signals")
    op.drop_table("approval_actions")
    op.drop_table("applications")
    op.drop_table("job_scores")
    op.drop_table("jobs")
    op.drop_table("oauth_tokens")
    op.drop_table("system_settings")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
