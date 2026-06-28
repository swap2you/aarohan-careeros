import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base


@pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="PostgreSQL required for migration tests",
)
def test_alembic_upgrade_downgrade_upgrade():
    from alembic import command
    from alembic.config import Config

    database_url = os.environ["DATABASE_URL"]
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
