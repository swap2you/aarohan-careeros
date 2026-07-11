#!/usr/bin/env python3
"""Owner OAuth validation after cutover."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import OAuthToken
from app.services.crypto import decrypt_payload
from app.services.google_api import _auth_headers, get_token, remediation_for_error
from app.services.owner_database_identity_preflight import validate_owner_database_identity


def _restart_owner_api() -> bool:
    subprocess.run(["docker", "restart", "aarohan-careeros-api-1"], capture_output=True, timeout=120, check=False)
    for _ in range(40):
        try:
            if httpx.get("http://127.0.0.1:8000/health", timeout=5.0).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--owner-email", default=os.environ.get("CAREER_GMAIL_ADDRESS", "swapnilpatil.tech@gmail.com"))
    args = parser.parse_args(argv)

    os.environ.setdefault("AAROHAN_DB_IDENTITY_PURPOSE", "OWNER")
    validate_owner_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    records = []
    try:
        rows = db.query(OAuthToken).filter(OAuthToken.provider == "google", OAuthToken.is_active.is_(True)).all()
        for row in rows:
            entry = {"service": row.service, "account_email": row.account_email, "decryptable": False, "refreshable": False}
            try:
                payload = decrypt_payload(row.encrypted_token)
                entry["decryptable"] = True
                entry["has_refresh_token"] = bool(payload.get("refresh_token"))
                live = get_token(db, row.service)
                entry["refreshable"] = bool(live and live.get("access_token"))
                if entry["refreshable"]:
                    with httpx.Client(timeout=20.0) as client:
                        g = client.get("https://gmail.googleapis.com/gmail/v1/users/me/profile", headers=_auth_headers(live))
                        d = client.get("https://www.googleapis.com/drive/v3/about", headers=_auth_headers(live), params={"fields": "user"})
                    entry["gmail_read_ok"] = g.status_code == 200
                    entry["drive_read_ok"] = d.status_code == 200
            except Exception as exc:
                entry["error"] = remediation_for_error(str(exc)) if "refresh" in str(exc).lower() else str(exc)[:200]
            records.append(entry)
    finally:
        db.close()
        engine.dispose()

    passed = (
        len(records) == 3
        and all(r.get("decryptable") and r.get("refreshable") and r.get("has_refresh_token") for r in records)
        and any(r.get("gmail_read_ok") for r in records)
        and any(r.get("drive_read_ok") for r in records)
    )
    restart_ok = _restart_owner_api()
    report = {
        "account": args.owner_email,
        "records": records,
        "restart_persistence": restart_ok,
        "passed": passed and restart_ok,
    }
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"passed": report["passed"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
