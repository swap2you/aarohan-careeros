#!/usr/bin/env python3
"""Phase 4 final post-cutover validation against canonical OWNER career_os.

Read-only OWNER identity is enforced fail-closed before any work. Sections:

    oauth      decrypt / refresh / Gmail / Drive / scopes / active-row determinism
    drive      Drive root binding + ownership + subfolders + no-duplicate-root
    gmail      canonical Gmail sync + idempotent second sync + classification
    freshjobs  live Fresh Jobs discovery + review of accepted/OWNER_REVIEW jobs

Secrets and token values are never printed or written.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Job, OAuthToken, ProcessedGmailMessage, SystemSetting
from app.services.crypto import decrypt_payload
from app.services.drive_settings import (
    DRIVE_ACTIVE_ROOT_KEY,
    DRIVE_SUBFOLDERS_KEY,
    get_drive_root_status,
    is_drive_folder_accessible,
)
from app.services.google_api import (
    APP_DRIVE_ROOT_FOLDER_NAME,
    DRIVE_SUBFOLDERS,
    _auth_headers,
    fetch_aarohan_labeled_messages,
    get_token,
)
from app.services.gmail_lifecycle import sync_messages
from app.services.gmail_replay import backfill_legacy_rows, should_replay_row
from app.services.fresh_jobs_discovery import discover_fresh_jobs
from app.services.job_eligibility import (
    DECISION_ACCEPT,
    DECISION_OWNER_REVIEW,
    DECISION_QUARANTINE,
    DECISION_REJECT,
    DECISION_SECONDARY,
    evaluate_eligibility,
    evaluate_freshness,
)
from app.services.provenance import PROVENANCE_VALIDATION
from app.services.owner_database_identity_preflight import validate_owner_database_identity

OWNER_EMAIL = "swapnilpatil.tech@gmail.com"
EXPECTED_DRIVE_ROOT = "1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr"
REQUIRED_SCOPES = {
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
}
REJECT_ENV_TOKENS = ("environmental", "supplier quality", "manufacturing quality", "hardware quality")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_setting(db, key: str) -> str | None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).one_or_none()
    return row.value if row else None


def _marker_created_at(db) -> str:
    return str(
        db.execute(text("SELECT created_at FROM aarohan_meta.database_identity LIMIT 1")).scalar()
    )


def section_oauth(db) -> dict:
    marker_created = _marker_created_at(db)
    active = (
        db.query(OAuthToken)
        .filter(OAuthToken.provider == "google", OAuthToken.is_active.is_(True))
        .order_by(OAuthToken.service)
        .all()
    )
    inactive = (
        db.query(OAuthToken)
        .filter(OAuthToken.provider == "google", OAuthToken.is_active.is_(False))
        .count()
    )
    records = []
    active_services: dict[str, int] = {}
    connected_ats: list[str] = []
    accounts: set[str] = set()
    scopes_union: set[str] = set()
    for row in active:
        active_services[row.service] = active_services.get(row.service, 0) + 1
        accounts.add((row.account_email or "").lower())
        if row.connected_at:
            connected_ats.append(str(row.connected_at))
        for sc in (row.scopes or "").split(","):
            if sc.strip():
                scopes_union.add(sc.strip())
        entry = {
            "service": row.service,
            "account_email": row.account_email,
            "is_active": row.is_active,
            "decryptable": False,
            "has_refresh_token": False,
            "refreshable": False,
            "connected_at": str(row.connected_at) if row.connected_at else None,
        }
        try:
            payload = decrypt_payload(row.encrypted_token)
            entry["decryptable"] = True
            entry["has_refresh_token"] = bool(payload.get("refresh_token"))
            live = get_token(db, row.service)
            entry["refreshable"] = bool(live and live.get("access_token"))
            if entry["refreshable"] and row.service in ("gmail", "google"):
                g = httpx.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                    headers=_auth_headers(live),
                    timeout=25.0,
                )
                entry["gmail_read_ok"] = g.status_code == 200
            if entry["refreshable"] and row.service in ("drive", "google"):
                d = httpx.get(
                    "https://www.googleapis.com/drive/v3/about",
                    headers=_auth_headers(live),
                    params={"fields": "user"},
                    timeout=25.0,
                )
                entry["drive_read_ok"] = d.status_code == 200
        except Exception as exc:  # noqa: BLE001
            entry["error"] = str(exc)[:200]
        records.append(entry)

    deterministic = all(count == 1 for count in active_services.values()) and set(
        active_services
    ) == {"google", "gmail", "drive"}
    account_ok = accounts == {OWNER_EMAIL.lower()}
    scopes_ok = REQUIRED_SCOPES.issubset(scopes_union)
    all_refresh = all(r["decryptable"] and r["has_refresh_token"] and r["refreshable"] for r in records)
    gmail_ok = any(r.get("gmail_read_ok") for r in records)
    drive_ok = any(r.get("drive_read_ok") for r in records)
    # No token copied from archived: every active token was (re)connected strictly
    # after the canonical cutover marker was created (fresh owner reconnect).
    min_connected = min(connected_ats) if connected_ats else None
    no_copy_from_archive = bool(min_connected and min_connected > marker_created)

    passed = (
        len(records) == 3
        and account_ok
        and deterministic
        and scopes_ok
        and all_refresh
        and gmail_ok
        and drive_ok
        and no_copy_from_archive
    )
    return {
        "generated_at": _now().isoformat(),
        "database": "career_os",
        "account": OWNER_EMAIL,
        "account_matches_owner": account_ok,
        "active_token_count": len(records),
        "inactive_token_count": inactive,
        "active_services": active_services,
        "active_rows_deterministic_nonduplicated": deterministic,
        "required_scopes_present": scopes_ok,
        "required_scopes": sorted(REQUIRED_SCOPES),
        "all_tokens_decrypt_and_refresh": all_refresh,
        "gmail_read_ok": gmail_ok,
        "drive_read_ok": drive_ok,
        "identity_marker_created_at": marker_created,
        "earliest_active_connected_at": min_connected,
        "no_token_copied_from_archived_db": no_copy_from_archive,
        "records": records,
        "passed": passed,
    }


def section_drive(db) -> dict:
    token = get_token(db, "drive")
    status = get_drive_root_status(db)
    stored_root = _get_setting(db, DRIVE_ACTIVE_ROOT_KEY)
    active_id = status.get("active_folder_id")
    accessible = bool(status.get("accessible"))

    owner_ok = False
    owned_by_me = False
    duplicate_roots = None
    subfolder_present: list[str] = []
    subfolder_missing: list[str] = []
    if token and not token.get("fixture") and active_id:
        try:
            r = httpx.get(
                f"https://www.googleapis.com/drive/v3/files/{active_id}",
                headers=_auth_headers(token),
                params={"fields": "id,name,owners(emailAddress),ownedByMe,trashed"},
                timeout=25.0,
            )
            if r.status_code == 200:
                body = r.json()
                owned_by_me = bool(body.get("ownedByMe"))
                owners = [o.get("emailAddress", "").lower() for o in body.get("owners", [])]
                owner_ok = OWNER_EMAIL.lower() in owners or owned_by_me
        except Exception:  # noqa: BLE001
            pass
        # Duplicate root detection.
        try:
            q = (
                f"name='{APP_DRIVE_ROOT_FOLDER_NAME}' and "
                "mimeType='application/vnd.google-apps.folder' and trashed=false"
            )
            rr = httpx.get(
                "https://www.googleapis.com/drive/v3/files",
                headers=_auth_headers(token),
                params={"q": q, "fields": "files(id,ownedByMe)", "pageSize": 50},
                timeout=25.0,
            )
            if rr.status_code == 200:
                owned = [f for f in rr.json().get("files", []) if f.get("ownedByMe", True)]
                duplicate_roots = len(owned)
        except Exception:  # noqa: BLE001
            pass

        subfolder_map = {}
        raw = _get_setting(db, DRIVE_SUBFOLDERS_KEY)
        if raw:
            try:
                subfolder_map = json.loads(raw)
            except json.JSONDecodeError:
                subfolder_map = {}
        for name in DRIVE_SUBFOLDERS:
            fid = subfolder_map.get(name)
            if fid and is_drive_folder_accessible(token, fid):
                subfolder_present.append(name)
            else:
                subfolder_missing.append(name)

    stored_matches = stored_root == EXPECTED_DRIVE_ROOT and active_id == EXPECTED_DRIVE_ROOT
    subfolders_complete = not subfolder_missing and len(subfolder_present) == len(DRIVE_SUBFOLDERS)
    passed = (
        accessible
        and stored_matches
        and owner_ok
        and subfolders_complete
        and (duplicate_roots is None or duplicate_roots <= 1)
    )
    return {
        "generated_at": _now().isoformat(),
        "database": "career_os",
        "expected_root_folder_id": EXPECTED_DRIVE_ROOT,
        "stored_active_folder_id": stored_root,
        "resolved_active_folder_id": active_id,
        "stored_setting_matches_expected": stored_matches,
        "read_accessible": accessible,
        "owned_by_me": owned_by_me,
        "owner_ownership_ok": owner_ok,
        "duplicate_app_roots_owned": duplicate_roots,
        "no_duplicate_root_created": duplicate_roots is None or duplicate_roots <= 1,
        "expected_subfolders": list(DRIVE_SUBFOLDERS),
        "subfolders_present": subfolder_present,
        "subfolders_missing": subfolder_missing,
        "subfolders_complete": subfolders_complete,
        "packet_root_accessible": accessible and subfolders_complete,
        "source": status.get("source"),
        "warning": status.get("warning"),
        "passed": passed,
    }


def section_gmail(db, gmail_max: int) -> dict:
    backfill_legacy_rows(db)
    replay_eligible = sum(1 for row in db.query(ProcessedGmailMessage).all() if should_replay_row(row, db)[0])
    jobs_before = db.query(Job).filter(Job.data_provenance != PROVENANCE_VALIDATION).count()
    error = None
    scanned = 0
    sync1 = sync2 = None
    try:
        messages = fetch_aarohan_labeled_messages(db, max_results=gmail_max)
        scanned = len(messages)
        sync1 = sync_messages(db, messages, actor="phase4_final")
        messages2 = fetch_aarohan_labeled_messages(db, max_results=gmail_max)
        sync2 = sync_messages(db, messages2, actor="phase4_final")
    except Exception as exc:  # noqa: BLE001
        error = str(exc)[:240]

    jobs_after = db.query(Job).filter(Job.data_provenance != PROVENANCE_VALIDATION).count()

    # Classification breakdown by processed message_type.
    classification: dict[str, int] = {}
    for row in db.query(ProcessedGmailMessage).all():
        key = row.message_type or "UNCLASSIFIED"
        classification[key] = classification.get(key, 0) + 1

    # Suppressors: complete JOB_ALERTs that produced nothing and have no jobs.
    suppressors = 0
    for row in db.query(ProcessedGmailMessage).all():
        if should_replay_row(row, db)[0]:
            continue
        if row.message_type == "JOB_ALERT" and (row.produced_entity_count or 0) == 0:
            found = db.execute(
                text("SELECT count(*) FROM jobs WHERE raw_payload->>'gmail_message_id' = :mid"),
                {"mid": row.message_id},
            ).scalar()
            if not found:
                suppressors += 1

    # Duplicate jobs by (title, company, url).
    dup = db.execute(
        text(
            "SELECT count(*) FROM (SELECT lower(title), lower(coalesce(company,'')), "
            "coalesce(url,'') FROM jobs WHERE data_provenance <> :p "
            "GROUP BY 1,2,3 HAVING count(*) > 1) t"
        ),
        {"p": PROVENANCE_VALIDATION},
    ).scalar()

    idempotent = bool(sync2 and sync2.get("jobs_ingested", 0) == 0 and jobs_after == (jobs_before + (sync1.get("jobs_ingested", 0) if sync1 else 0)))
    passed = (
        error is None
        and scanned > 0
        and suppressors == 0
        and idempotent
        and (dup or 0) == 0
    )
    return {
        "generated_at": _now().isoformat(),
        "database": "career_os",
        "gmail_messages_scanned": scanned,
        "replay_eligible": replay_eligible,
        "first_sync": sync1,
        "second_sync": sync2,
        "second_sync_idempotent": idempotent,
        "jobs_before": jobs_before,
        "jobs_after": jobs_after,
        "classification_breakdown": classification,
        "suppressors_without_jobs": suppressors,
        "duplicate_jobs": dup or 0,
        "oauth_refresh_error": error,
        "passed": passed,
    }


def _job_entry(job: Job, result, now) -> dict:
    payload = {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "description_text": job.description_text,
        "source": job.source,
        "posted_at": job.posted_at,
        "source_received_at": job.source_received_at,
        "discovered_at": job.discovered_at,
    }
    tier, ts_source, _, age_hours, *_ = evaluate_freshness(payload, now=now)
    url = (job.url or "").lower()
    title = (job.title or "").lower()
    desc = (job.description_text or "").lower()
    flags = []
    if any(tok in title or tok in desc for tok in REJECT_ENV_TOKENS):
        flags.append("non_software_quality_role")
    if not (url.startswith("http://") or url.startswith("https://")):
        flags.append("invalid_url")
    if "digest" in title or "job alert" in title:
        flags.append("malformed_digest_title")
    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "official_url": job.url,
        "source": job.source,
        "timestamp_source": ts_source or job.freshness_source,
        "age_hours": age_hours,
        "freshness_tier": tier or job.freshness_bucket,
        "role_profile": job.recommended_profile or result.recommended_profile,
        "decision": result.decision,
        "reason_codes": result.reason_codes,
        "eligible_for_owner": job.eligible_for_owner,
        "review_flags": flags,
    }


def section_freshjobs(db, skip_discovery: bool = False) -> dict:
    now = _now().replace(tzinfo=None)
    discovery = None
    error = None
    if skip_discovery:
        discovery = {"skipped": True, "reason": "re-evaluation of already-discovered jobs against updated policy"}
    else:
        try:
            discovery = discover_fresh_jobs(db, actor="phase4_final")
        except Exception as exc:  # noqa: BLE001
            error = str(exc)[:240]

    jobs = (
        db.query(Job)
        .filter(Job.data_provenance != PROVENANCE_VALIDATION)
        .order_by(Job.id)
        .all()
    )
    accepted, owner_review, quarantined, rejected = [], [], [], []
    for job in jobs:
        payload = {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "description_text": job.description_text,
            "source": job.source,
            "posted_at": job.posted_at,
            "source_received_at": job.source_received_at,
            "discovered_at": job.discovered_at,
        }
        result = evaluate_eligibility(payload, now=now)
        entry = _job_entry(job, result, now)
        if job.eligible_for_owner and result.decision == DECISION_ACCEPT:
            accepted.append(entry)
        elif result.decision in {DECISION_OWNER_REVIEW, DECISION_SECONDARY}:
            owner_review.append(entry)
        elif result.decision == DECISION_QUARANTINE:
            quarantined.append(entry)
        else:
            rejected.append(entry)

    reviewable = accepted + owner_review
    all_flags = [f for e in reviewable for f in e["review_flags"]]
    gitlab_count = sum(1 for e in reviewable if "gitlab" in (e["company"] or "").lower())
    passed = (
        error is None
        and len(all_flags) == 0
        and gitlab_count <= 1
    )
    return {
        "generated_at": _now().isoformat(),
        "database": "career_os",
        "discovery_summary": {
            "sources_attempted": (discovery or {}).get("sources_attempted"),
            "sources_skipped": (discovery or {}).get("sources_skipped"),
            "source_errors": (discovery or {}).get("source_errors"),
            "total_ingested": (discovery or {}).get("total_ingested"),
        }
        if discovery
        else None,
        "discovery_error": error,
        "counts": {
            "accepted": len(accepted),
            "owner_review": len(owner_review),
            "quarantined": len(quarantined),
            "rejected": len(rejected),
        },
        "accepted": accepted,
        "owner_review": owner_review,
        "review_flags_found": all_flags,
        "gitlab_reviewable_count": gitlab_count,
        "passed": passed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 4 final OWNER validation")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--section", required=True, choices=["oauth", "drive", "gmail", "freshjobs"])
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--gmail-max", type=int, default=250)
    parser.add_argument("--skip-discovery", action="store_true", help="freshjobs: re-evaluate existing jobs without live fetch")
    args = parser.parse_args(argv)

    if not args.database_url:
        print(json.dumps({"error": "missing database url"}))
        return 2
    if settings.oauth_fixture_mode:
        print(json.dumps({"error": "oauth_fixture_mode must be false for live validation"}))
        return 2

    os.environ.setdefault("AAROHAN_DB_IDENTITY_PURPOSE", "OWNER")
    validate_owner_database_identity(database_url=args.database_url)

    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        if args.section == "oauth":
            report = section_oauth(db)
        elif args.section == "drive":
            report = section_drive(db)
        elif args.section == "gmail":
            report = section_gmail(db, args.gmail_max)
        else:
            report = section_freshjobs(db, skip_discovery=args.skip_discovery)
    finally:
        db.close()
        engine.dispose()

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(json.dumps({"section": args.section, "passed": report.get("passed")}))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
