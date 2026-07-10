"""Add immutable aarohan_meta.database_identity marker."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_database_identity_meta"
down_revision = "0012_fresh_jobs_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS aarohan_meta")
    op.create_table(
        "database_identity",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("identity_uuid", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("identity_uuid", name="uq_database_identity_uuid"),
        schema="aarohan_meta",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION aarohan_meta.enforce_database_identity_rules()
        RETURNS trigger AS $$
        BEGIN
          IF TG_OP IN ('UPDATE', 'DELETE') THEN
            RAISE EXCEPTION 'aarohan_meta.database_identity is immutable';
          END IF;
          IF TG_OP = 'INSERT' THEN
            IF (SELECT count(*) FROM aarohan_meta.database_identity) > 0 THEN
              RAISE EXCEPTION 'only one aarohan_meta.database_identity row allowed';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_database_identity_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON aarohan_meta.database_identity
        FOR EACH ROW EXECUTE FUNCTION aarohan_meta.enforce_database_identity_rules();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_database_identity_immutable ON aarohan_meta.database_identity")
    op.execute("DROP FUNCTION IF EXISTS aarohan_meta.enforce_database_identity_rules()")
    op.drop_table("database_identity", schema="aarohan_meta")
    op.execute("DROP SCHEMA IF EXISTS aarohan_meta CASCADE")
