#!/usr/bin/env python3
"""Validate a verified backup manifest matches the current owner identity."""

from __future__ import annotations

import argparse
import json
import sys

from app.services.owner_database_identity_preflight import (
    OwnerIdentityPreflightError,
    OwnerIdentityPreflightResult,
    assert_same_run_backup_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate same-run backup manifest binding")
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--dump-path", default="")
    parser.add_argument("--same-run-started-at", default="")
    parser.add_argument("--identity-json", required=True, help="JSON from owner identity preflight")
    args = parser.parse_args(argv)

    try:
        identity_payload = json.loads(args.identity_json)
        identity = OwnerIdentityPreflightResult(
            verified=bool(identity_payload["verified"]),
            purpose=str(identity_payload["purpose"]),
            identity_uuid=str(identity_payload["identity_uuid"]),
            database=str(identity_payload["database"]),
            compose_project=str(identity_payload["compose_project"]),
            postgres_service=str(identity_payload["postgres_service"]),
            postgres_container=str(identity_payload["postgres_container"]),
            host=str(identity_payload["host"]),
            port=int(identity_payload["port"]),
            privileged_user=str(identity_payload["privileged_user"]),
            identity_fingerprint=str(identity_payload["identity_fingerprint"]),
            verified_at=str(identity_payload["verified_at"]),
        )
        assert_same_run_backup_manifest(
            args.manifest_path,
            identity=identity,
            dump_path=args.dump_path or None,
            same_run_started_at=args.same_run_started_at or None,
        )
    except OwnerIdentityPreflightError as exc:
        print(json.dumps({"verified": False, "error": str(exc)}), flush=True)
        return 1
    except Exception as exc:
        print(json.dumps({"verified": False, "error": str(exc)}), flush=True)
        return 1

    print(json.dumps({"verified": True}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
