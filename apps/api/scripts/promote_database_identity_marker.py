#!/usr/bin/env python3
"""Guarded OWNER identity marker promotion — disposable cutover rehearsal only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from app.services.database_identity import (
    PURPOSE_OWNER,
    PURPOSE_OWNER_CANDIDATE,
    assert_destructive_token,
    load_database_identity_record,
    validate_database_identity_marker,
)
from app.services.database_identity import assert_identity_configured  # noqa: E402

REQUIRED_PHRASE = "APPROVE OWNER CANDIDATE CUTOVER"


def promote_marker(
    bootstrap_url: str,
    *,
    candidate_uuid: str,
    new_owner_uuid: str,
    confirmation_phrase: str,
    destructive_token: str,
) -> dict:
    if confirmation_phrase != REQUIRED_PHRASE:
        raise RuntimeError(f"Confirmation phrase must be exactly: {REQUIRED_PHRASE}")
    assert_destructive_token("identity marker promotion", destructive_token)

    engine = create_engine(bootstrap_url, pool_pre_ping=True)
    steps: list[dict] = []
    try:
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            before = load_database_identity_record(engine)
            steps.append({
                "step": "before_marker",
                "purpose": before.purpose,
                "identity_uuid": str(before.identity_uuid),
            })
            if before.purpose != PURPOSE_OWNER_CANDIDATE:
                raise RuntimeError(f"Expected OWNER_CANDIDATE marker, found {before.purpose}")
            if before.identity_uuid.lower() != candidate_uuid.lower():
                raise RuntimeError("Candidate UUID mismatch on marker row")

            conn.execute(
                text(
                    "ALTER TABLE aarohan_meta.database_identity "
                    "DISABLE TRIGGER trg_database_identity_immutable"
                )
            )
            conn.execute(text("DELETE FROM aarohan_meta.database_identity"))
            conn.execute(
                text(
                    """
                    INSERT INTO aarohan_meta.database_identity
                        (purpose, identity_uuid, schema_version, created_at)
                    VALUES (:purpose, :identity_uuid, :schema_version, NOW())
                    """
                ),
                {
                    "purpose": PURPOSE_OWNER,
                    "identity_uuid": new_owner_uuid,
                    "schema_version": "0013",
                },
            )
            conn.execute(
                text(
                    "ALTER TABLE aarohan_meta.database_identity "
                    "ENABLE TRIGGER trg_database_identity_immutable"
                )
            )
            after = load_database_identity_record(engine)
            steps.append({
                "step": "after_marker",
                "purpose": after.purpose,
                "identity_uuid": str(after.identity_uuid),
            })
            if after.purpose != PURPOSE_OWNER or after.identity_uuid.lower() != new_owner_uuid.lower():
                raise RuntimeError("Marker promotion did not persist expected OWNER row")
    finally:
        engine.dispose()

    return {
        "promoted": True,
        "candidate_uuid": candidate_uuid,
        "new_owner_uuid": new_owner_uuid,
        "steps": steps,
    }


def verify_marker_expectation(database_url: str, *, purpose: str, identity_uuid: str) -> bool:
    os.environ["AAROHAN_DB_IDENTITY_PURPOSE"] = purpose
    os.environ["AAROHAN_DB_IDENTITY_UUID"] = identity_uuid
    assert_identity_configured()
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        validate_database_identity_marker(engine, database_url)
        return True
    except Exception as exc:
        return False
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote OWNER_CANDIDATE marker to OWNER")
    parser.add_argument("--bootstrap-url", required=True)
    parser.add_argument("--runtime-url", required=True)
    parser.add_argument("--candidate-uuid", required=True)
    parser.add_argument("--new-owner-uuid", required=True)
    parser.add_argument("--confirmation-phrase", default=os.environ.get("CUTOVER_REHEARSAL_PHRASE", ""))
    parser.add_argument("--destructive-token", default=os.environ.get("AAROHAN_DESTRUCTIVE_TOKEN", ""))
    parser.add_argument("--output-json")
    args = parser.parse_args(argv)

    result = promote_marker(
        args.bootstrap_url,
        candidate_uuid=args.candidate_uuid,
        new_owner_uuid=args.new_owner_uuid,
        confirmation_phrase=args.confirmation_phrase,
        destructive_token=args.destructive_token,
    )
    result["owner_validation_passes"] = verify_marker_expectation(
        args.runtime_url, purpose=PURPOSE_OWNER, identity_uuid=args.new_owner_uuid
    )
    result["candidate_validation_fails"] = not verify_marker_expectation(
        args.runtime_url, purpose=PURPOSE_OWNER_CANDIDATE, identity_uuid=args.candidate_uuid
    )
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    if args.output_json:
        os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    print(json.dumps({"promoted": True, "owner_validation_passes": result["owner_validation_passes"]}))
    return 0 if result["owner_validation_passes"] and result["candidate_validation_fails"] else 1


if __name__ == "__main__":
    sys.exit(main())
