"""Align FK nullability with ORM models.

Revision ID: 0003_fk_not_null
Revises: 0002_google_tracking
Create Date: 2026-06-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_fk_not_null"
down_revision = "0002_google_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("applications", "job_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("approval_actions", "application_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("interview_packs", "job_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("job_scores", "job_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.alter_column("job_scores", "job_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("interview_packs", "job_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("approval_actions", "application_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("applications", "job_id", existing_type=sa.Integer(), nullable=True)
