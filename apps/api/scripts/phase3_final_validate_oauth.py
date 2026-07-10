#!/usr/bin/env python3
"""Final candidate OAuth validation with restart persistence and duplicate disposition."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

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


def _restart_candidate_api() -> tuple[bool, str | None]:
    try:
        proc = subprocess.run(
            ["docker", "restart", "aarohan-candidate-api"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout)[:200]
        for _ in range(30):
            try:
                resp = httpx.get("http://127.0.0.1:8002/health", timeout=5.0)
                if resp.status_code == 200:
                    return True, None
            except Exception:
                pass
            time.sleep(2)
        return False, "candidate API health timeout after restart"
    except Exception as exc:
        return False, str(exc)[:200]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Final candidate OAuth validation")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--owner-email", default=settings.career_gmail_address or "")
    parser.add_argument("--restart-check", action="store_true", default=True)
    args = parser.parse_args(argv)

    if not args.database_url or settings.oauth_fixture_mode:
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
            .order_by(OAuthToken.connected_at.desc(), OAuthToken.id.desc())
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
                reason_exclude = "superseded duplicate (provider, service, account_email)"
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
                    refresh_error = remediation_for_error(str(exc))
                if refreshable and live:
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
                "selected": row.is_active and owner_match and decryptable and refreshable and has_refresh,
            }
            records.append(entry)
            if entry["selected"]:
                selected.append(entry)

        pre_count = len([r for r in records if r["refreshable"]])
        restart_ok = None
        restart_error = None
        post_refreshable = pre_count
        if args.restart_check and selected:
            restart_ok, restart_error = _restart_candidate_api()
            post_refreshable = 0
            db_refresh = Session()
            try:
                for row in all_tokens:
                    if not row.is_active:
                        continue
                    try:
                        live = get_token(db_refresh, row.service)
                        if live and live.get("access_token"):
                            post_refreshable += 1
                    except Exception:
                        pass
            finally:
                db_refresh.close()
    finally:
        db.close()
        engine.dispose()

    selected_google = [r for r in selected if r["service"] in {"google", "gmail"}]
    owner_rows = [r for r in records if r["owner_identity_match"]]
    passed = (
        len(selected) >= 1
        and all(r["decryptable"] and r["refreshable"] and r["has_refresh_token"] for r in selected)
        and all(r.get("gmail_read_ok") for r in selected_google)
        and any(r.get("drive_read_ok") for r in selected if r["service"] in {"google", "drive"})
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account": args.owner_email,
        "scopes": selected[0]["scope_names"] if selected else (owner_rows[0]["scope_names"] if owner_rows else []),
        "refresh_token_present": all(r["has_refresh_token"] for r in owner_rows) if owner_rows else False,
        "decryptable": all(r["decryptable"] for r in owner_rows) if owner_rows else False,
        "refreshable": all(r["refreshable"] for r in owner_rows) if owner_rows else False,
        "gmail_health": all(r["gmail_read_ok"] for r in selected_google) if selected_google else False,
        "drive_health": any(r["drive_read_ok"] for r in selected if r["service"] in {"google", "drive"}),
        "restart_persistence": {
            "restarted": restart_ok,
            "error": restart_error,
            "refreshable_before": pre_count,
            "refreshable_after": post_refreshable,
            "passed": restart_ok is not False and post_refreshable >= 1,
        },
        "duplicate_token_disposition": {
            "selected_count": len(selected),
            "excluded_count": len(excluded),
            "selected_services": sorted({r["service"] for r in selected}),
            "excluded": excluded,
        },
        "selected_records_redacted": selected,
        "all_records_redacted": records,
        "passed": passed,
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"passed": passed, "selected": len(selected)}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
