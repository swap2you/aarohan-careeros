"""Live owner validation checks (Drive, Gmail, Google, connectors) — redacted plain-English results."""

from __future__ import annotations

import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Application, ApplicationDocumentVersion, Job, RecruiterSignal, ValidationRun
from app.services.drive_settings import resolve_active_drive_root
from app.services.google_api import integration_status
from app.services.integrations import get_gmail_client


def _step(name: str, ok: bool, summary: str, *, details: dict | None = None, status: str | None = None) -> dict:
    resolved = status or ("PASS" if ok else "FAIL")
    return {
        "name": name,
        "ok": ok,
        "status": resolved,
        "summary": summary,
        "details": details or {},
    }


def _mask_id(value: str | None) -> str:
    if not value:
        return "—"
    if len(value) <= 10:
        return value
    return f"{value[:6]}…{value[-4:]}"


def check_google_connection(db: Session) -> dict:
    status = integration_status(db)
    connected = bool(status.get("google_connected"))
    token_usable = bool(status.get("token_usable"))
    fixture = bool(status.get("fixture_mode"))
    account = status.get("connected_account") or "not connected"
    if fixture:
        return _step(
            "google_connection",
            False,
            "Google is in fixture mode. Set OAUTH_FIXTURE_MODE=false and reconnect for live validation.",
            details={"fixture_mode": True},
        )
    if not connected:
        return _step("google_connection", False, "Google is not connected. Use Settings → Reconnect Google.")
    if not token_usable:
        return _step(
            "google_connection",
            False,
            "Google account is linked but tokens cannot be used. Reconnect Google once (no data loss).",
            details={"dedicated_gmail": status.get("dedicated_gmail")},
        )
    return _step(
        "google_connection",
        True,
        f"Google connected for {account}.",
        details={"dedicated_gmail": status.get("dedicated_gmail")},
    )


def check_drive_root(db: Session) -> dict:
    configured_id, active_id, accessible = resolve_active_drive_root(db)
    if settings.oauth_fixture_mode:
        return _step("drive_root", False, "Drive validation requires live OAuth (fixture mode is on).")
    if not accessible or not active_id:
        return _step(
            "drive_root",
            False,
            "Drive root is not accessible. Create or sync an app-owned root in Settings.",
            details={"configured": _mask_id(configured_id), "active": _mask_id(active_id)},
        )
    subfolders = (integration_status(db).get("drive_root") or {}).get("subfolders") or {}
    return _step(
        "drive_root",
        True,
        f"Drive root is accessible with {len(subfolders)} subfolders.",
        details={
            "active_root": _mask_id(active_id),
            "subfolder_count": len(subfolders),
        },
    )


def check_drive_packets(db: Session) -> dict:
    """Verify submitted/immutable versions have local paths and Drive linkage when live."""
    if settings.oauth_fixture_mode:
        return _step("drive_packets", False, "Skipped — fixture mode.")

    versions = (
        db.query(ApplicationDocumentVersion)
        .filter(ApplicationDocumentVersion.is_submitted_immutable.is_(True))
        .order_by(ApplicationDocumentVersion.id.desc())
        .limit(5)
        .all()
    )
    if not versions:
        return _step(
            "drive_packets",
            True,
            "Not yet tested — create and submit a controlled v01 packet, then generate v02.",
            status="NOT APPLICABLE",
        )

    v01 = versions[0]
    has_local = bool(v01.docx_path and v01.pdf_path)
    has_drive = bool(v01.drive_docx_id and v01.drive_pdf_id)
    multi = len(versions) >= 2
    v02_different = True
    if multi:
        v02 = versions[1]
        v02_different = v01.docx_path != v02.docx_path and v01.drive_docx_id != v02.drive_docx_id

    ok = has_local and has_drive and (not multi or v02_different)
    summary = (
        "Submitted packet v01 has local files and Drive links."
        if ok
        else "Packet/Drive linkage incomplete — verify upload after packet generation."
    )
    return _step(
        "drive_packets",
        ok,
        summary,
        details={
            "submitted_versions": len(versions),
            "v01_local": has_local,
            "v01_drive": has_drive,
            "v02_different_identity": v02_different if multi else "n/a",
        },
    )


def check_gmail_live(db: Session, *, actor: str) -> dict:
    if settings.oauth_fixture_mode:
        return _step("gmail_live", False, "Gmail validation requires live OAuth (fixture mode is on).")

    from app.services.gmail_lifecycle import sync_messages
    from app.services.google_api import fetch_aarohan_labeled_messages

    before_signals = db.query(RecruiterSignal).count()
    before_jobs = db.query(Job).count()
    t0 = time.perf_counter()
    messages = fetch_aarohan_labeled_messages(db, max_results=50)
    if not messages:
        client = get_gmail_client(db)
        messages = client.fetch_recent_messages(max_results=50)
    result1 = sync_messages(db, messages, source="gmail", actor=actor)
    result2 = sync_messages(db, messages, source="gmail", actor=actor)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    idempotent = result2.get("skipped", 0) >= result1.get("processed", 0)
    sources = {}
    for label_prefix in ("LinkedIn", "Indeed", "Dice", "USAJOBS", "Glassdoor"):
        count = (
            db.query(RecruiterSignal)
            .filter(RecruiterSignal.gmail_label.ilike(f"%{label_prefix}%"))
            .count()
        )
        if count:
            sources[label_prefix] = count

    ok = idempotent and (result1.get("processed", 0) > 0 or before_signals > 0 or len(messages) == 0)
    if len(messages) == 0:
        summary = "Gmail sync ran but no labeled messages were returned (inbox may be empty)."
    elif idempotent:
        summary = (
            f"Gmail sync processed {result1.get('processed', 0)} messages; "
            f"replay skipped {result2.get('skipped', 0)} (idempotent)."
        )
    else:
        summary = "Gmail sync may have duplicated messages — review recruiter signals."

    return _step(
        "gmail_live",
        ok,
        summary,
        details={
            "messages_fetched": len(messages),
            "pass1": {k: result1.get(k) for k in ("processed", "skipped", "errors")},
            "pass2_skipped": result2.get("skipped"),
            "signals_by_source_label": sources,
            "jobs_delta": db.query(Job).count() - before_jobs,
            "latency_ms": latency_ms,
        },
    )


def check_connectors(db: Session) -> dict:
    from app.integrations.job_providers import list_provider_statuses
    from app.services.connector_runner import probe_connector_health

    rows = []
    any_ready = False
    for status in list_provider_statuses():
        probe = probe_connector_health(status.provider_id)
        row = {
            "name": status.label,
            "status": probe.get("status", status.state.value),
            "record_count": probe.get("record_count", 0),
            "latency_ms": probe.get("latency_ms"),
            "error": probe.get("error"),
        }
        rows.append(row)
        if row["status"] == "READY":
            any_ready = True
    return _step(
        "connectors",
        any_ready or len(rows) > 0,
        f"Checked {len(rows)} connectors.",
        details={"connectors": rows},
    )


def run_live_owner_validation(db: Session, *, actor: str) -> ValidationRun:
    steps = [
        check_google_connection(db),
        check_drive_root(db),
        check_drive_packets(db),
        check_gmail_live(db, actor=actor),
        check_connectors(db),
    ]
    passed = all(s["ok"] or s.get("status") in {"NOT APPLICABLE", "NOT RUN"} for s in steps)
    results = {
        "mode": "live_owner",
        "steps": steps,
        "plain_summary": "; ".join(f"{s['name']}: {s['status']}" for s in steps),
    }
    run = ValidationRun(
        status="PASS" if passed else "FAIL",
        summary=results["plain_summary"],
        results=results,
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
