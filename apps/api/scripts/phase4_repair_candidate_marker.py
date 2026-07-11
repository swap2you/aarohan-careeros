#!/usr/bin/env python3
"""Restore OWNER_CANDIDATE marker after failed cutover rollback."""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text

CANDIDATE_UUID = "78010e56-041c-4fec-b8f7-0f9ca313d267"


def main() -> int:
    pw = os.environ.get("POSTGRES_PASSWORD", "")
    if not pw:
        return 1
    url = f"postgresql+psycopg://career_os:{pw}@127.0.0.1:5432/career_os_owner_candidate"
    engine = create_engine(url)
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(text("ALTER TABLE aarohan_meta.database_identity DISABLE TRIGGER trg_database_identity_immutable"))
        conn.execute(text("DELETE FROM aarohan_meta.database_identity"))
        conn.execute(
            text(
                """
                INSERT INTO aarohan_meta.database_identity
                    (purpose, identity_uuid, schema_version, created_at)
                VALUES ('OWNER_CANDIDATE', :uuid, '0013', NOW())
                """
            ),
            {"uuid": CANDIDATE_UUID},
        )
        conn.execute(text("ALTER TABLE aarohan_meta.database_identity ENABLE TRIGGER trg_database_identity_immutable"))
        row = conn.execute(text("SELECT purpose, identity_uuid FROM aarohan_meta.database_identity")).one()
        print({"purpose": row[0], "identity_uuid": str(row[1])})
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
