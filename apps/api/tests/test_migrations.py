import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base


def _reprovision_identity_marker(database_url: str) -> None:
    purpose = os.getenv("AAROHAN_DB_IDENTITY_PURPOSE")
    identity_uuid = os.getenv("AAROHAN_DB_IDENTITY_UUID")
    if not purpose or not identity_uuid:
        return
    bootstrap_url = os.getenv("BOOTSTRAP_DATABASE_URL") or database_url
    if "career_os_e2e" in database_url:
        os.environ.setdefault("E2E_MIGRATE_PASSWORD", os.getenv("E2E_MIGRATE_PASSWORD", ""))
        os.environ.setdefault("E2E_RUNTIME_PASSWORD", os.getenv("E2E_RUNTIME_PASSWORD", ""))
    engine = create_engine(bootstrap_url, pool_pre_ping=True)
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT to_regclass('aarohan_meta.database_identity')")).scalar()
        if not exists:
            return
        count = conn.execute(text("SELECT count(*) FROM aarohan_meta.database_identity")).scalar()
        if count:
            return
    from scripts.provision_database_roles import provision_e2e, provision_owner

    if "career_os_e2e" in database_url:
        provision_e2e(
            bootstrap_url,
            os.environ["E2E_MIGRATE_PASSWORD"],
            os.environ["E2E_RUNTIME_PASSWORD"],
            purpose,
            identity_uuid,
        )
    else:
        provision_owner(
            bootstrap_url,
            os.environ["POSTGRES_MIGRATE_PASSWORD"],
            os.environ["POSTGRES_RUNTIME_PASSWORD"],
            purpose,
            identity_uuid,
        )


def _reset_schema(database_url: str) -> None:
    from tests.postgres_utils import reset_public_schema

    engine = create_engine(database_url)
    reset_public_schema(engine)


@pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="PostgreSQL required for migration tests",
)
def test_alembic_upgrade_downgrade_upgrade():
    from alembic import command
    from alembic.config import Config

    database_url = os.getenv("MIGRATION_DATABASE_URL") or os.environ["DATABASE_URL"]
    _reset_schema(database_url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(cfg, "head")
    engine = create_engine(database_url)
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        ).fetchall()
        names = {row[0] for row in tables}
        assert "jobs" in names
        assert "processed_gmail_messages" in names

    command.downgrade(cfg, "base")
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        ).fetchall()
        assert "jobs" not in {row[0] for row in tables}

    command.upgrade(cfg, "head")
    _reprovision_identity_marker(database_url)
