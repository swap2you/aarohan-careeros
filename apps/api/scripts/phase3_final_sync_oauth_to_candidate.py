#!/usr/bin/env python3
"""Copy fresh owner OAuth rows into candidate DB (read-only on career_os)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import AuditLog, OAuthToken
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity

FORBIDDEN_TARGETS = {"career_os", "career_os_validation"}


def _db_name(url: str) -> str:
    return url.rsplit("/", 1)[-1].split("?")[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync OAuth tokens to candidate from owner source")
    parser.add_argument("--candidate-url", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--owner-email", default=os.environ.get("CAREER_GMAIL_ADDRESS", "swapnilpatil.tech@gmail.com"))
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    if _db_name(args.candidate_url) in FORBIDDEN_TARGETS:
        print("Refusing to write OAuth into forbidden database", file=sys.stderr)
        return 2
    if _db_name(args.source_url) not in {"career_os"}:
        print("Source must be career_os read-only", file=sys.stderr)
        return 2

    validate_recovery_database_identity(database_url=args.candidate_url)

    source_engine = create_engine(args.source_url)
    target_engine = create_engine(args.candidate_url)
    Source = sessionmaker(bind=source_engine)
    Target = sessionmaker(bind=target_engine)
    source = Source()
    target = Target()

    try:
        fresh = (
            source.query(OAuthToken)
            .filter(OAuthToken.provider == "google", OAuthToken.is_active.is_(True))
            .order_by(OAuthToken.connected_at.desc(), OAuthToken.id.desc())
            .all()
        )
        owner_rows = [r for r in fresh if (r.account_email or "").lower() == args.owner_email.lower()]
        if not owner_rows:
            report = {"synced": False, "reason": "no active owner google tokens in source", "copied": 0}
            with open(args.output_json, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            return 1

        seen: set[tuple[str, str, str]] = set()
        selected: list[OAuthToken] = []
        for row in owner_rows:
            key = ((row.provider or "").lower(), (row.service or "").lower(), (row.account_email or "").lower())
            if key in seen:
                continue
            seen.add(key)
            selected.append(row)

        target.query(OAuthToken).filter(OAuthToken.provider == "google").delete(synchronize_session=False)
        copied = 0
        for row in selected:
            target.add(
                OAuthToken(
                    provider=row.provider,
                    service=row.service,
                    account_email=row.account_email,
                    encrypted_token=row.encrypted_token,
                    scopes=row.scopes,
                    connected_at=row.connected_at,
                    expires_at=row.expires_at,
                    is_active=True,
                )
            )
            copied += 1
        target.add(
            AuditLog(
                event_type="oauth.connected",
                actor=args.owner_email,
                resource_type="oauth",
                resource_id="google",
                details={"synced_from": "career_os", "phase": "phase3_final"},
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        target.commit()
        report = {
            "synced": True,
            "copied": copied,
            "services": sorted({r.service for r in selected}),
            "source_connected_at": max(r.connected_at.isoformat() for r in selected),
            "note": "Read-only copy from career_os; career_os unchanged",
        }
    except Exception as exc:
        target.rollback()
        report = {"synced": False, "reason": str(exc)[:200], "copied": 0}
        with open(args.output_json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        return 1
    finally:
        source.close()
        target.close()
        source_engine.dispose()
        target_engine.dispose()

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
