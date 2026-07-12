#!/usr/bin/env python3
"""Workflow 01.5 §3 — read-only Gmail alert coverage audit.

Audits how well the canonical owner Gmail integration is represented in Aarohan, WITHOUT
mutating processed state. It classifies persisted ``processed_gmail_messages`` rows and their
job linkage, reports parser coverage by message type, and (optionally, with ``--live``)
searches recent Gmail for known alert senders and classifies each as processed / absent.

Privacy: only redacted message-id prefixes and subject *classifications* are emitted — never
raw email bodies, subjects, addresses, or tokens.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime

ALERT_SENDER_QUERIES = {
    "linkedin": "from:jobalerts-noreply@linkedin.com OR from:jobs-noreply@linkedin.com",
    "indeed": "from:alert@indeed.com OR from:donotreply@indeed.com",
    "dice": "from:alerts@dice.com",
    "usajobs": "from:donotreply@usajobs.gov OR from:usajobs@usajobs.gov",
    "glassdoor": "from:noreply@glassdoor.com",
}


def _redact(message_id: str | None) -> str:
    if not message_id:
        return "—"
    return f"{str(message_id)[:10]}…"


def _db_audit(db) -> dict:
    from app.models import Job, ProcessedGmailMessage

    rows = db.query(ProcessedGmailMessage).all()
    by_status: Counter = Counter()
    by_type: Counter = Counter()
    replay_required = 0
    with_output = 0
    without_output = 0
    parser_versions: Counter = Counter()
    for row in rows:
        by_status[row.processing_status or "UNKNOWN"] += 1
        by_type[row.message_type or "UNSPECIFIED"] += 1
        parser_versions[row.parser_version or "none"] += 1
        if row.replay_required:
            replay_required += 1
        if (row.produced_entity_count or 0) > 0 or row.produced_entity_type:
            with_output += 1
        else:
            without_output += 1

    # Jobs linked to a gmail message via raw_payload.gmail_message_id
    gmail_jobs = (
        db.query(Job).filter(Job.data_provenance == "gmail").all()
    )
    linked_message_ids = set()
    for job in gmail_jobs:
        raw = job.raw_payload or {}
        if isinstance(raw, dict) and raw.get("gmail_message_id"):
            linked_message_ids.add(str(raw["gmail_message_id"]))

    return {
        "processed_gmail_messages_total": len(rows),
        "by_processing_status": dict(by_status),
        "by_message_type": dict(by_type),
        "parser_version_distribution": dict(parser_versions),
        "replay_required_count": replay_required,
        "messages_with_job_output": with_output,
        "messages_without_job_output": without_output,
        "gmail_provenance_jobs": len(gmail_jobs),
        "distinct_linked_gmail_message_ids": len(linked_message_ids),
        "parser_coverage_by_type": {
            k: v for k, v in by_type.items() if k not in {"UNSPECIFIED"}
        },
    }


def _live_audit(db, max_results: int) -> dict:
    """Best-effort live Gmail search for alert senders. Never mutates processed state."""
    from app.models import ProcessedGmailMessage

    try:
        from app.services.google_api import fetch_gmail_messages
    except Exception as exc:  # pragma: no cover
        return {"available": False, "error": f"import_failed: {str(exc)[:120]}"}

    processed_ids = {r.message_id for r in db.query(ProcessedGmailMessage.message_id).all()}
    per_sender: dict[str, dict] = {}
    for sender, query in ALERT_SENDER_QUERIES.items():
        try:
            messages = fetch_gmail_messages(db, query=query, max_results=max_results)
        except Exception as exc:
            per_sender[sender] = {"error": str(exc)[:160], "found": 0}
            continue
        found = len(messages)
        present = 0
        absent_ids = []
        for msg in messages:
            mid = str(msg.get("id") or msg.get("message_id") or "")
            if mid and mid in processed_ids:
                present += 1
            else:
                absent_ids.append(_redact(mid))
        per_sender[sender] = {
            "found": found,
            "already_processed": present,
            "absent_from_aarohan": len(absent_ids),
            "absent_message_id_prefixes": absent_ids[:25],
        }
    return {"available": True, "per_sender": per_sender}


def run_audit(db, *, live: bool = False, max_results: int = 50) -> dict:
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "mutated_processed_state": False,
        "db_coverage": _db_audit(db),
    }
    if live:
        report["live_gmail"] = _live_audit(db, max_results)
    else:
        report["live_gmail"] = {"available": False, "note": "run with --live for a Gmail API search"}
    # Explicit reasons a visible Gmail alert may be absent from Aarohan.
    report["absence_reasons_reference"] = [
        "ignored_by_gmail_query (sender/label not in Aarohan query)",
        "outside_current_time_window",
        "parser_unsupported (sender/template has no parser)",
        "malformed (unparseable body)",
        "duplicate (canonical URL / provider id / fingerprint match)",
        "non_job_lifecycle_message (recruiter/interview/confirmation)",
        "processed_without_output (parsed, no eligible job produced)",
        "replay_required (processed but flagged for replay)",
    ]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Gmail alert coverage audit")
    parser.add_argument("--live", action="store_true", help="also search Gmail API for alert senders")
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args(argv)

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        report = run_audit(db, live=args.live, max_results=args.max_results)
    finally:
        db.close()
    payload = json.dumps(report, indent=2, default=str)
    print(payload)
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as fh:
            fh.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
