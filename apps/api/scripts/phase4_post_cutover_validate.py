#!/usr/bin/env python3
"""Post-cutover owner validation on canonical career_os."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Job, OAuthToken, User
from app.services.crypto import decrypt_payload
from app.services.drive_settings import get_drive_root_status
from app.services.google_api import _auth_headers, get_token, remediation_for_error
from app.services.owner_database_identity_preflight import validate_owner_database_identity
from app.services.provenance import PROVENANCE_VALIDATION

E2E_EMAIL = "e2e@test.local"


def _gmail_ok(token_data: dict) -> tuple[bool, str | None]:
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers=_auth_headers(token_data),
            )
        return resp.status_code == 200, None if resp.status_code == 200 else remediation_for_error(resp.text)
    except Exception as exc:
        return False, str(exc)


def _drive_ok(token_data: dict) -> tuple[bool, str | None]:
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                "https://www.googleapis.com/drive/v3/about",
                headers=_auth_headers(token_data),
                params={"fields": "user"},
            )
        return resp.status_code == 200, None if resp.status_code == 200 else remediation_for_error(resp.text)
    except Exception as exc:
        return False, str(exc)


def _restart_owner_api() -> tuple[bool, str | None]:
    proc = subprocess.run(
        ["docker", "restart", "aarohan-careeros-api-1"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout)[:200]
    for _ in range(40):
        try:
            if httpx.get("http://127.0.0.1:8000/health", timeout=5.0).status_code == 200:
                return True, None
        except Exception:
            pass
        time.sleep(2)
    return False, "owner API health timeout after restart"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 4 post-cutover validation")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--report-md", required=True)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--admin-email", default=os.environ.get("ADMIN_EMAIL", ""))
    parser.add_argument("--admin-password", default=os.environ.get("ADMIN_PASSWORD", ""))
    args = parser.parse_args(argv)

    os.environ["AAROHAN_DB_IDENTITY_PURPOSE"] = "OWNER"
    identity = validate_owner_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    defects: list[dict] = []
    checks: dict = {}

    try:
        if db.query(User).filter(User.is_admin.is_(True)).count() != 1:
            defects.append({"severity": "critical", "check": "single_admin"})
        if db.query(User).filter(func.lower(User.email) == E2E_EMAIL).count():
            defects.append({"severity": "critical", "check": "no_e2e_user"})

        oauth_rows = db.query(OAuthToken).filter(OAuthToken.provider == "google", OAuthToken.is_active.is_(True)).all()
        checks["oauth_active_count"] = len(oauth_rows)
        if len(oauth_rows) != 3:
            defects.append({"severity": "high", "check": "oauth_triple", "detail": f"count={len(oauth_rows)}"})

        refreshable = 0
        gmail_ok = False
        drive_ok = False
        for row in oauth_rows:
            try:
                payload = decrypt_payload(row.encrypted_token)
                if not payload.get("refresh_token"):
                    continue
                live = get_token(db, row.service)
                if live and live.get("access_token"):
                    refreshable += 1
                    g, _ = _gmail_ok(live)
                    d, _ = _drive_ok(live)
                    gmail_ok = gmail_ok or g
                    drive_ok = drive_ok or d
            except Exception:
                continue
        checks["oauth_refreshable"] = refreshable >= 3
        checks["gmail_health"] = gmail_ok
        checks["drive_health"] = drive_ok
        if refreshable < 3:
            defects.append({"severity": "high", "check": "oauth_refresh"})
        if not gmail_ok:
            defects.append({"severity": "high", "check": "gmail_read"})
        if not drive_ok:
            defects.append({"severity": "high", "check": "drive_read"})

        drive_resolved = False
        drive_warning = None
        try:
            drive_status = get_drive_root_status(db)
            drive_resolved = bool(drive_status.get("active_folder_id")) and bool(drive_status.get("accessible"))
            drive_warning = drive_status.get("warning")
        except Exception as exc:
            drive_warning = str(exc)[:200]
        checks["drive_resolved"] = drive_resolved
        if not drive_resolved:
            defects.append({"severity": "high", "check": "drive_root", "detail": drive_warning})

        checks["accepted_jobs"] = db.query(Job).filter(Job.eligible_for_owner.is_(True)).count()
        checks["total_jobs"] = db.query(Job).filter(Job.data_provenance != PROVENANCE_VALIDATION).count()
        if checks["accepted_jobs"] < 1:
            defects.append({"severity": "medium", "check": "fresh_jobs_accepted"})

        restart_ok, restart_err = _restart_owner_api()
        checks["restart_persistence"] = restart_ok
        if not restart_ok:
            defects.append({"severity": "high", "check": "restart", "detail": restart_err})

        post_restart = 0
        db2 = Session()
        try:
            for row in oauth_rows:
                try:
                    live = get_token(db2, row.service)
                    if live and live.get("access_token"):
                        post_restart += 1
                except Exception:
                    pass
        finally:
            db2.close()
        checks["oauth_refreshable_after_restart"] = post_restart >= 3
        if post_restart < 3:
            defects.append({"severity": "high", "check": "oauth_after_restart"})

        try:
            login = httpx.post(
                f"{args.api_base}/api/auth/login",
                json={"email": args.admin_email, "password": args.admin_password},
                timeout=20.0,
            )
            checks["login_status"] = login.status_code
            if login.status_code != 200:
                defects.append({"severity": "high", "check": "login", "detail": str(login.status_code)})
            else:
                token = login.json().get("access_token")
                jobs = httpx.get(
                    f"{args.api_base}/api/jobs",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=20.0,
                )
                checks["jobs_api_status"] = jobs.status_code
                if jobs.status_code != 200:
                    defects.append({"severity": "high", "check": "jobs_api"})
        except Exception as exc:
            defects.append({"severity": "high", "check": "login_exception", "detail": str(exc)[:200]})

        try:
            health = httpx.get(f"{args.api_base}/health", timeout=10.0)
            checks["api_health"] = health.status_code == 200
        except Exception:
            checks["api_health"] = False
            defects.append({"severity": "high", "check": "api_health"})

        checks["identity"] = identity.to_dict()
    finally:
        db.close()
        engine.dispose()

    passed = not any(d["severity"] in {"critical", "high"} for d in defects)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "checks": checks,
        "defects": defects,
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    lines = [
        "# Phase 4 Post-Cutover Validation Report",
        "",
        f"- **Passed:** {passed}",
        f"- **Defects:** {len(defects)}",
        "",
        "## Checks",
        "",
        f"```json\n{json.dumps(checks, indent=2)}\n```",
    ]
    Path(args.report_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "defects": len(defects)}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
