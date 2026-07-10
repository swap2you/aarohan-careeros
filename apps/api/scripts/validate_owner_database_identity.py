#!/usr/bin/env python3
"""CLI for owner database identity preflight (used by PowerShell helpers)."""

from __future__ import annotations

import argparse
import json
import sys

from app.services.owner_database_identity_preflight import (
    OwnerIdentityPreflightError,
    validate_owner_database_identity,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate owner database identity before privileged operations")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--database", default="career_os")
    parser.add_argument("--compose-project", default="aarohan-careeros")
    parser.add_argument("--postgres-service", default="postgres")
    parser.add_argument("--postgres-container", default="")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--privileged-user", default="career_os")
    args = parser.parse_args(argv)

    try:
        result = validate_owner_database_identity(
            database_url=args.database_url,
            database=args.database,
            compose_project=args.compose_project,
            postgres_service=args.postgres_service,
            postgres_container=args.postgres_container,
            host=args.host,
            port=args.port,
            privileged_user=args.privileged_user,
        )
    except OwnerIdentityPreflightError as exc:
        print(json.dumps({"verified": False, "error": str(exc)}), flush=True)
        return 1

    print(json.dumps(result.to_dict()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
