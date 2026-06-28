"""Migration 0005: trust matching and explainability fields."""

from alembic import op
import sqlalchemy as sa

revision = "0005_trust_matching"
down_revision = "0004_duplicate_protection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("role_family", sa.String(64), nullable=True))
    op.add_column("jobs", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("is_expired", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("jobs", sa.Column("source_verified", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("jobs", sa.Column("match_summary", sa.Text(), nullable=True))
    op.create_index("ix_jobs_role_family", "jobs", ["role_family"])
    op.create_index("ix_jobs_is_expired", "jobs", ["is_expired"])

    op.add_column("job_scores", sa.Column("trust_score", sa.Float(), nullable=True))
    op.add_column("job_scores", sa.Column("trust_reasons", sa.JSON(), nullable=True))
    op.add_column("job_scores", sa.Column("fit_reasons", sa.JSON(), nullable=True))
    op.add_column("job_scores", sa.Column("hard_filter_passed", sa.Boolean(), nullable=True))
    op.add_column("job_scores", sa.Column("hard_filter_reasons", sa.JSON(), nullable=True))
    op.add_column("job_scores", sa.Column("match_card", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_scores", "match_card")
    op.drop_column("job_scores", "hard_filter_reasons")
    op.drop_column("job_scores", "hard_filter_passed")
    op.drop_column("job_scores", "fit_reasons")
    op.drop_column("job_scores", "trust_reasons")
    op.drop_column("job_scores", "trust_score")
    op.drop_index("ix_jobs_is_expired", table_name="jobs")
    op.drop_index("ix_jobs_role_family", table_name="jobs")
    op.drop_column("jobs", "match_summary")
    op.drop_column("jobs", "source_verified")
    op.drop_column("jobs", "is_expired")
    op.drop_column("jobs", "expires_at")
    op.drop_column("jobs", "role_family")
