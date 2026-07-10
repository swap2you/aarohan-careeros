#!/usr/bin/env python3
"""Validate candidate OAuth tokens: decrypt, refresh, Gmail/Drive read health."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import OAuthToken
from app.services.crypto import decrypt_payload
from app.services.google_api import _auth_headers, get_token, remediation_for_error
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity

E2E_EMAIL = "e2e@test.local"
FIXTURE_MARKERS = ("fixture", "test@", "e2e@")


def _scope_names(scopes_csv: str | None) -> list[str]:
    return sorted({s.strip() for s in (scopes_csv or "").split(",") if s.strip()})


def _gmail_read_ok(token_data: dict) -> tuple[bool, str | None]:
    if token_data.get("fixture"):
        return False, "fixture mode"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers=_auth_headers(token_data),
            )
        if resp.status_code == 200:
            return True, None
        return False, remediation_for_error(resp.text)
    except Exception as exc:
        return False, str(exc)


def _drive_read_ok(token_data: dict) -> tuple[bool, str | None]:
    if token_data.get("fixture"):
        return False, "fixture mode"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                "https://www.googleapis.com/drive/v3/about",
                headers=_auth_headers(token_data),
                params={"fields": "user"},
            )
        if resp.status_code == 200:
            return True, None
        return False, remediation_for_error(resp.text)
    except Exception as exc:
        return False, str(exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Candidate OAuth validation")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--owner-email", default=settings.career_gmail_address or "")
    args = parser.parse_args(argv)

    if not args.database_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1
    if settings.oauth_fixture_mode:
        print("Refusing OAuth validation in fixture mode", file=sys.stderr)
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    records: list[dict] = []
    excluded: list[dict] = []
    selected: list[dict] = []

    try:
        all_tokens = (
            db.query(OAuthToken)
            .filter(OAuthToken.provider == "google")
            .order_by(OAuthToken.id.desc())
            .all()
        )
        seen_keys: set[tuple[str, str, str]] = set()
        for row in all_tokens:
            email = (row.account_email or "").lower()
            key = ((row.provider or "").lower(), (row.service or "").lower(), email)
            reason_exclude = None
            if email == E2E_EMAIL:
                reason_exclude = "e2e test account"
            elif any(m in email for m in FIXTURE_MARKERS):
                reason_exclude = "fixture/test email marker"
            elif not row.is_active:
                reason_exclude = "inactive row"
            elif key in seen_keys:
                reason_exclude = "duplicate (provider, service, account_email)"
            if reason_exclude:
                excluded.append({
                    "id": row.id,
                    "provider": row.provider,
                    "service": row.service,
                    "account_email": row.account_email,
                    "reason": reason_exclude,
                })
                continue
            seen_keys.add(key)

            decryptable = False
            refreshable = False
            has_refresh = False
            decrypt_error = None
            refresh_error = None
            try:
                payload = decrypt_payload(row.encrypted_token)
                decryptable = True
                has_refresh = bool(payload.get("refresh_token"))
            except Exception as exc:
                decrypt_error = str(exc)

            gmail_ok = False
            drive_ok = False
            gmail_error = None
            drive_error = None
            if decryptable and row.is_active:
                try:
                    live = get_token(db, row.service)
                    refreshable = bool(live and live.get("access_token"))
                except Exception as exc:
                    refresh_error = str(exc)
                if refreshable:
                    gmail_ok, gmail_error = _gmail_read_ok(live)
                    drive_ok, drive_error = _drive_read_ok(live)

            owner_match = email == (args.owner_email or "").lower()
            entry = {
                "id": row.id,
                "provider": row.provider,
                "service": row.service,
                "account_email": row.account_email,
                "owner_identity_match": owner_match,
                "scope_names": _scope_names(row.scopes),
                "decryptable": decryptable,
                "has_refresh_token": has_refresh,
                "refreshable": refreshable,
                "gmail_read_ok": gmail_ok,
                "drive_read_ok": drive_ok,
                "decrypt_error_redacted": decrypt_error,
                "refresh_error_redacted": refresh_error,
                "gmail_error_redacted": gmail_error,
                "drive_error_redacted": drive_error,
                "selected": row.is_active and owner_match and decryptable and refreshable,
            }
            records.append(entry)
            if entry["selected"]:
                selected.append(entry)
    finally:
        db.close()
        engine.dispose()

    passed = bool(selected) and all(
        r["decryptable"] and r["refreshable"] and r.get("gmail_read_ok")
        for r in selected
        if r["service"] in {"google", "gmail"}
    )
    decryptable_owner_rows = [r for r in records if r["owner_identity_match"] and r["decryptable"]]
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "owner_email_expected": args.owner_email,
        "passed": passed,
        "decryptable_owner_tokens": len(decryptable_owner_rows),
        "requires_owner_reconnect": any(
            r["decryptable"] and not r["has_refresh_token"] for r in decryptable_owner_rows
        ),
        "selected_count": len(selected),
        "excluded_count": len(excluded),
        "selected_records": selected,
        "excluded_duplicates": excluded,
        "all_records_redacted": records,
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"passed": passed, "selected": len(selected)}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
