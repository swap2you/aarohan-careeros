"""R2.8 interview intelligence extensions."""

from alembic import op
import sqlalchemy as sa

revision = "0009_r28_interview_intel"
down_revision = "0008_r27_gmail_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interview_packs", sa.Column("interview_rounds", sa.JSON(), nullable=True))
    op.add_column("interview_packs", sa.Column("negotiation_prep", sa.JSON(), nullable=True))
    op.add_column("interview_packs", sa.Column("document_links", sa.JSON(), nullable=True))
    op.add_column("interview_packs", sa.Column("recruiter_timeline", sa.JSON(), nullable=True))
    op.add_column("interview_packs", sa.Column("gaps_and_risks", sa.JSON(), nullable=True))


def downgrade() -> None:
    for col in ("gaps_and_risks", "recruiter_timeline", "document_links", "negotiation_prep", "interview_rounds"):
        op.drop_column("interview_packs", col)
