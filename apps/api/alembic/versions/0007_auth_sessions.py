"""Auth sessions and OAuth persistence metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0007_auth_sessions"
down_revision = "0006_r25_manual_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("remember_me", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.add_column("oauth_tokens", sa.Column("last_refresh_at", sa.DateTime(), nullable=True))
    op.add_column("oauth_tokens", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("oauth_tokens", sa.Column("connection_status", sa.String(32), server_default="connected", nullable=False))


def downgrade() -> None:
    op.drop_column("oauth_tokens", "connection_status")
    op.drop_column("oauth_tokens", "last_error")
    op.drop_column("oauth_tokens", "last_refresh_at")
    op.drop_table("auth_sessions")
