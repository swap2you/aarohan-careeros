#!/usr/bin/env python3
"""Idempotent PostgreSQL role and identity marker provisioning."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from app.services.database_identity import (
    E2E_MIGRATE_USER,
    E2E_RUNTIME_USER,
    OWNER_MIGRATE_USER,
    OWNER_RUNTIME_USER,
    PURPOSE_CI,
    PURPOSE_E2E,
    PURPOSE_OWNER,
    UUID_PATTERN,
)


def _q(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _role_attrs(engine, role: str) -> dict[str, bool]:
    row = engine.connect().execute(
        text(
            """
            SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
            FROM pg_roles WHERE rolname = :role
            """
        ),
        {"role": role},
    ).one_or_none()
    if row is None:
        return {}
    return {
        "rolsuper": bool(row.rolsuper),
        "rolcreatedb": bool(row.rolcreatedb),
        "rolcreaterole": bool(row.rolcreaterole),
        "rolreplication": bool(row.rolreplication),
        "rolbypassrls": bool(row.rolbypassrls),
    }


def _escape_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _ensure_role(conn, role: str, password: str) -> None:
    exists = conn.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
    ).scalar()
    password_sql = _escape_literal(password)
    if not exists:
        conn.execute(
            text(
                f"CREATE ROLE {_q(role)} LOGIN PASSWORD {password_sql} "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            )
        )
    else:
        conn.execute(
            text(
                f"ALTER ROLE {_q(role)} WITH LOGIN PASSWORD {password_sql} "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            )
        )


def _grant_runtime_privileges(
    conn, runtime_role: str, migrate_role: str, database: str, schemas: tuple[str, ...] = ("public",)
) -> None:
    conn.execute(text(f"GRANT CONNECT ON DATABASE {_q(database)} TO {_q(runtime_role)}"))
    for schema in schemas:
        exists = conn.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = :schema"), {"schema": schema}
        ).scalar()
        if not exists:
            continue
        conn.execute(text(f"GRANT USAGE ON SCHEMA {_q(schema)} TO {_q(runtime_role)}"))
        conn.execute(
            text(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {_q(schema)} TO {_q(runtime_role)}"
            )
        )
        conn.execute(
            text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {_q(schema)} TO {_q(runtime_role)}")
        )
        conn.execute(text(f"REVOKE CREATE ON SCHEMA {_q(schema)} FROM {_q(runtime_role)}"))
        conn.execute(
            text(
                f"""
                ALTER DEFAULT PRIVILEGES FOR ROLE {_q(migrate_role)} IN SCHEMA {_q(schema)}
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {_q(runtime_role)}
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER DEFAULT PRIVILEGES FOR ROLE {_q(migrate_role)} IN SCHEMA {_q(schema)}
                GRANT USAGE, SELECT ON SEQUENCES TO {_q(runtime_role)}
                """
            )
        )


def _reassign_application_objects(
    conn, bootstrap_role: str, migrate_role: str, schemas: tuple[str, ...] = ("public", "aarohan_meta")
) -> None:
    for schema in schemas:
        exists = conn.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = :schema"), {"schema": schema}
        ).scalar()
        if exists:
            conn.execute(text(f"ALTER SCHEMA {_q(schema)} OWNER TO {_q(migrate_role)}"))
    schema_list = ", ".join(_escape_literal(schema) for schema in schemas)
    rows = conn.execute(
        text(
            f"""
            SELECT n.nspname AS schema_name, c.relname AS object_name, c.relkind
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_roles r ON r.oid = c.relowner
            WHERE r.rolname = :bootstrap
              AND n.nspname IN ({schema_list})
              AND c.relkind IN ('r', 'v', 'f', 'p')
            """
        ),
        {"bootstrap": bootstrap_role},
    ).fetchall()
    kind_map = {"r": "TABLE", "v": "VIEW", "f": "FUNCTION", "p": "PROCEDURE"}
    for schema_name, object_name, relkind in rows:
        kind = kind_map.get(relkind)
        if not kind:
            continue
        try:
            conn.execute(
                text(f"ALTER {kind} {_q(schema_name)}.{_q(object_name)} OWNER TO {_q(migrate_role)}")
            )
        except Exception:
            continue


def _grant_migrate_privileges(conn, migrate_role: str, bootstrap_role: str, database: str) -> None:
    conn.execute(text(f"GRANT CONNECT, CREATE ON DATABASE {_q(database)} TO {_q(migrate_role)}"))
    for schema in ("public", "aarohan_meta"):
        exists = conn.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = :schema"), {"schema": schema}
        ).scalar()
        if not exists:
            continue
        conn.execute(text(f"GRANT USAGE, CREATE ON SCHEMA {_q(schema)} TO {_q(migrate_role)}"))
        conn.execute(
            text(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {_q(schema)} TO {_q(migrate_role)}")
        )
        conn.execute(
            text(f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {_q(schema)} TO {_q(migrate_role)}")
        )
        conn.execute(
            text(f"GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA {_q(schema)} TO {_q(migrate_role)}")
        )
    _reassign_application_objects(conn, bootstrap_role, migrate_role)
    conn.execute(text(f"REVOKE CREATE ON SCHEMA public FROM {_q(bootstrap_role)}"))
    conn.execute(
        text(
            f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE {_q(migrate_role)} IN SCHEMA public
            GRANT ALL ON TABLES TO {_q(migrate_role)}
            """
        )
    )


def _ensure_meta_schema(conn, migrate_role: str, runtime_role: str) -> None:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS aarohan_meta"))
    conn.execute(text(f"ALTER SCHEMA aarohan_meta OWNER TO {_q(migrate_role)}"))
    conn.execute(
        text(
            f"GRANT USAGE ON SCHEMA aarohan_meta TO {_q(runtime_role)}, {_q(migrate_role)}"
        )
    )
    conn.execute(
        text(
            f"GRANT SELECT ON ALL TABLES IN SCHEMA aarohan_meta TO {_q(runtime_role)}"
        )
    )
    conn.execute(
        text(
            f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA aarohan_meta TO {_q(migrate_role)}"
        )
    )
    conn.execute(
        text(
            f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE {_q(migrate_role)} IN SCHEMA aarohan_meta
            GRANT SELECT ON TABLES TO {_q(runtime_role)}
            """
        )
    )


def _ensure_identity_marker(
    conn,
    migrate_role: str,
    purpose: str,
    identity_uuid: str,
    schema_version: str = "0013",
) -> None:
    if not UUID_PATTERN.match(identity_uuid):
        raise RuntimeError("identity_uuid must be a valid UUID")
    exists = conn.execute(
        text("SELECT to_regclass('aarohan_meta.database_identity')")
    ).scalar()
    if not exists:
        raise RuntimeError(
            "aarohan_meta.database_identity missing; run alembic upgrade before provisioning."
        )
    count = conn.execute(text("SELECT count(*) FROM aarohan_meta.database_identity")).scalar()
    if count == 0:
        conn.execute(text(f"SET ROLE {_q(migrate_role)}"))
        conn.execute(
            text(
                """
                INSERT INTO aarohan_meta.database_identity
                    (purpose, identity_uuid, schema_version, created_at)
                VALUES (:purpose, :identity_uuid, :schema_version, :created_at)
                """
            ),
            {
                "purpose": purpose,
                "identity_uuid": identity_uuid,
                "schema_version": schema_version,
                "created_at": datetime.now(timezone.utc),
            },
        )
        conn.execute(text("RESET ROLE"))
        return
    row = conn.execute(
        text(
            "SELECT purpose, identity_uuid FROM aarohan_meta.database_identity ORDER BY id LIMIT 1"
        )
    ).one()
    if str(row.purpose).upper() != purpose.upper() or str(row.identity_uuid).lower() != identity_uuid.lower():
        raise RuntimeError(
            "Existing aarohan_meta.database_identity does not match requested purpose/uuid."
        )


def provision_owner(
  bootstrap_url: str,
  migrate_password: str,
  runtime_password: str,
  purpose: str,
  identity_uuid: str,
) -> dict:
    engine = create_engine(bootstrap_url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        _ensure_role(conn, OWNER_MIGRATE_USER, migrate_password)
        _ensure_role(conn, OWNER_RUNTIME_USER, runtime_password)
        _grant_migrate_privileges(conn, OWNER_MIGRATE_USER, "career_os", "career_os")
        _grant_runtime_privileges(
            conn, OWNER_RUNTIME_USER, OWNER_MIGRATE_USER, "career_os", ("public", "aarohan_meta")
        )
        _ensure_meta_schema(conn, OWNER_MIGRATE_USER, OWNER_RUNTIME_USER)
        _ensure_identity_marker(conn, OWNER_MIGRATE_USER, purpose, identity_uuid)
    return {
        "stack": "owner",
        "migrate_role": OWNER_MIGRATE_USER,
        "runtime_role": OWNER_RUNTIME_USER,
        "migrate_attrs": _role_attrs(engine, OWNER_MIGRATE_USER),
        "runtime_attrs": _role_attrs(engine, OWNER_RUNTIME_USER),
        "purpose": purpose,
        "identity_uuid": identity_uuid,
    }


def provision_e2e(
    bootstrap_url: str,
    migrate_password: str,
    runtime_password: str,
    purpose: str,
    identity_uuid: str,
) -> dict:
    engine = create_engine(bootstrap_url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        _ensure_role(conn, E2E_MIGRATE_USER, migrate_password)
        _ensure_role(conn, E2E_RUNTIME_USER, runtime_password)
        _grant_migrate_privileges(conn, E2E_MIGRATE_USER, "career_os_e2e", "career_os_e2e")
        _grant_runtime_privileges(
            conn, E2E_RUNTIME_USER, E2E_MIGRATE_USER, "career_os_e2e", ("public", "aarohan_meta")
        )
        _ensure_meta_schema(conn, E2E_MIGRATE_USER, E2E_RUNTIME_USER)
        _ensure_identity_marker(conn, E2E_MIGRATE_USER, purpose, identity_uuid)
    return {
        "stack": "e2e",
        "migrate_role": E2E_MIGRATE_USER,
        "runtime_role": E2E_RUNTIME_USER,
        "migrate_attrs": _role_attrs(engine, E2E_MIGRATE_USER),
        "runtime_attrs": _role_attrs(engine, E2E_RUNTIME_USER),
        "purpose": purpose,
        "identity_uuid": identity_uuid,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provision PostgreSQL roles and identity marker")
    parser.add_argument("--stack", choices=["owner", "e2e", "ci"], required=True)
    args = parser.parse_args(argv)

    if args.stack == "owner":
        bootstrap_url = os.environ["BOOTSTRAP_DATABASE_URL"]
        migrate_password = os.environ["POSTGRES_MIGRATE_PASSWORD"]
        runtime_password = os.environ["POSTGRES_RUNTIME_PASSWORD"]
        purpose = os.environ.get("AAROHAN_DB_IDENTITY_PURPOSE", PURPOSE_OWNER)
        identity_uuid = os.environ["AAROHAN_DB_IDENTITY_UUID"]
        result = provision_owner(
            bootstrap_url, migrate_password, runtime_password, purpose, identity_uuid
        )
    elif args.stack == "e2e":
        bootstrap_url = os.environ["BOOTSTRAP_DATABASE_URL"]
        migrate_password = os.environ["E2E_MIGRATE_PASSWORD"]
        runtime_password = os.environ["E2E_RUNTIME_PASSWORD"]
        purpose = os.environ.get("AAROHAN_DB_IDENTITY_PURPOSE", PURPOSE_E2E)
        identity_uuid = os.environ["AAROHAN_DB_IDENTITY_UUID"]
        result = provision_e2e(
            bootstrap_url, migrate_password, runtime_password, purpose, identity_uuid
        )
    else:
        bootstrap_url = os.environ["BOOTSTRAP_DATABASE_URL"]
        migrate_password = os.environ.get("POSTGRES_MIGRATE_PASSWORD", "testmigrate")
        runtime_password = os.environ.get("POSTGRES_RUNTIME_PASSWORD", "testruntime")
        purpose = os.environ.get("AAROHAN_DB_IDENTITY_PURPOSE", PURPOSE_CI)
        identity_uuid = os.environ["AAROHAN_DB_IDENTITY_UUID"]
        result = provision_owner(
            bootstrap_url, migrate_password, runtime_password, purpose, identity_uuid
        )

    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
