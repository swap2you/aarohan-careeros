"""Durable Gmail processed-message replay semantics for recovery and live sync."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Job, ProcessedGmailMessage, RecruiterSignal

GMAIL_PARSER_VERSION = "2.0.0"

STATUS_LEGACY = "LEGACY"
STATUS_COMPLETE = "COMPLETE"
STATUS_REPLAY_REQUIRED = "REPLAY_REQUIRED"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"

ENTITY_JOB = "job"
ENTITY_RECRUITER_SIGNAL = "recruiter_signal"
ENTITY_NONE = "none"

REPLAY_CLASS_VALID_COMPLETE = "VALID_COMPLETE"
REPLAY_CLASS_REPLAY_REQUIRED_JOB_ALERT = "REPLAY_REQUIRED_JOB_ALERT"
REPLAY_CLASS_REPLAY_REQUIRED_OTHER = "REPLAY_REQUIRED_OTHER"
REPLAY_CLASS_MALFORMED = "MALFORMED"
REPLAY_CLASS_NON_JOB_LIFECYCLE = "NON_JOB_LIFECYCLE"
REPLAY_CLASS_EXCLUDE_TEST_FIXTURE = "EXCLUDE_TEST_FIXTURE"

JOB_ALERT_TYPES = {"JOB_ALERT"}
NON_JOB_LIFECYCLE_TYPES = {
    "RECRUITER_OUTREACH",
    "APPLICATION_CONFIRMATION",
    "ASSESSMENT",
    "INTERVIEW",
    "REJECTION",
    "OFFER",
    "FOLLOW_UP",
    "UNRELATED",
}


def _legacy_row_needs_replay(row: ProcessedGmailMessage, db: Session) -> tuple[bool, str]:
    """Infer replay need for rows imported before replay columns existed."""
    if (row.message_id or "").startswith("fixture-"):
        return False, "fixture message id"
    signal = (
        db.query(RecruiterSignal)
        .filter(RecruiterSignal.gmail_message_id == row.message_id)
        .one_or_none()
    )
    if signal and signal.signal_type != "JOB_ALERT":
        return False, "non-job lifecycle signal exists"
    if signal and signal.job_id:
        job = db.query(Job).filter(Job.id == signal.job_id).one_or_none()
        if job:
            return False, "job output exists"
    jobs_from_gmail = (
        db.query(Job)
        .filter(text("raw_payload->>'gmail_message_id' = :mid"))
        .params(mid=row.message_id)
        .count()
    )
    if jobs_from_gmail:
        return False, "job linked via raw_payload"
    # Processed with no surviving job output — eligible for replay
    return True, "processed without surviving job output"


def should_skip_gmail_fetch(row: ProcessedGmailMessage | None, db: Session) -> bool:
    """Return True when fetch/sync should skip this message (not eligible for replay)."""
    if row is None:
        return False
    if row.replay_required:
        return False
    if row.processing_status == STATUS_REPLAY_REQUIRED:
        return False
    if row.processing_status == STATUS_LEGACY:
        needs, _ = _legacy_row_needs_replay(row, db)
        return not needs
    if row.processing_status in {STATUS_COMPLETE, STATUS_SKIPPED}:
        if row.produced_entity_type == ENTITY_JOB and row.produced_entity_count > 0:
            return True
        if row.message_type in NON_JOB_LIFECYCLE_TYPES:
            return True
        if row.produced_entity_type == ENTITY_RECRUITER_SIGNAL and row.produced_entity_count > 0:
            return True
        # Complete but zero output for job alert — allow replay
        if row.message_type == "JOB_ALERT" and row.produced_entity_count == 0:
            return False
        return row.produced_entity_count > 0
    return False


def should_replay_row(row: ProcessedGmailMessage, db: Session) -> tuple[bool, str]:
    if row.replay_required:
        return True, row.replay_reason or "replay_required flag set"
    if row.processing_status == STATUS_REPLAY_REQUIRED:
        return True, row.replay_reason or "status replay_required"
    if row.parser_version and row.parser_version != GMAIL_PARSER_VERSION:
        if row.message_type == "JOB_ALERT":
            return True, f"parser version {row.parser_version} != {GMAIL_PARSER_VERSION}"
    if row.processing_status == STATUS_LEGACY:
        return _legacy_row_needs_replay(row, db)
    if row.processing_status == STATUS_COMPLETE and row.message_type == "JOB_ALERT":
        if row.produced_entity_count == 0:
            return True, "complete job alert with zero output"
    return False, "no replay needed"


def classify_processed_row(row: ProcessedGmailMessage, db: Session) -> dict:
    message_id = row.message_id or ""
    if message_id.startswith("fixture-") or "fixture" in message_id.lower():
        return _classification(row, REPLAY_CLASS_EXCLUDE_TEST_FIXTURE, "fixture message id")

    signal = (
        db.query(RecruiterSignal)
        .filter(RecruiterSignal.gmail_message_id == message_id)
        .one_or_none()
    )
    msg_type = row.message_type or (signal.signal_type if signal else None)

    if signal and signal.signal_type != "JOB_ALERT":
        return _classification(row, REPLAY_CLASS_NON_JOB_LIFECYCLE, f"signal_type={signal.signal_type}")

    if msg_type in NON_JOB_LIFECYCLE_TYPES and msg_type != "JOB_ALERT":
        return _classification(row, REPLAY_CLASS_NON_JOB_LIFECYCLE, f"message_type={msg_type}")

    needs_replay, reason = should_replay_row(row, db)
    if needs_replay:
        if msg_type == "JOB_ALERT" or (signal is None and row.processing_status == STATUS_LEGACY):
            return _classification(row, REPLAY_CLASS_REPLAY_REQUIRED_JOB_ALERT, reason)
        return _classification(row, REPLAY_CLASS_REPLAY_REQUIRED_OTHER, reason)

    if row.processing_status == STATUS_FAILED:
        return _classification(row, REPLAY_CLASS_MALFORMED, row.last_processing_result or "failed processing")

    if row.produced_entity_count > 0 or (signal and signal.job_id):
        return _classification(row, REPLAY_CLASS_VALID_COMPLETE, "output exists")

    return _classification(row, REPLAY_CLASS_MALFORMED, "processed without output")


def _classification(row: ProcessedGmailMessage, replay_class: str, reason: str) -> dict:
    return {
        "message_id": row.message_id,
        "classification": replay_class,
        "reason": reason,
        "message_type": row.message_type,
        "parser_version": row.parser_version,
        "processing_status": row.processing_status,
        "produced_entity_type": row.produced_entity_type,
        "produced_entity_count": row.produced_entity_count,
        "replay_required": row.replay_required,
    }


def upsert_processing_record(
    db: Session,
    message_id: str,
    *,
    message_type: str | None = None,
    parser_version: str | None = None,
    processing_status: str = STATUS_COMPLETE,
    produced_entity_type: str | None = None,
    produced_entity_id: str | None = None,
    produced_entity_count: int = 0,
    last_processing_result: str | None = None,
    replay_required: bool = False,
    replay_reason: str | None = None,
) -> ProcessedGmailMessage:
    row = (
        db.query(ProcessedGmailMessage)
        .filter(ProcessedGmailMessage.message_id == message_id)
        .one_or_none()
    )
    now = datetime.utcnow()
    if not row:
        row = ProcessedGmailMessage(message_id=message_id, processed_at=now)
        db.add(row)
    row.message_type = message_type or row.message_type
    row.parser_version = parser_version or GMAIL_PARSER_VERSION
    row.processing_status = processing_status
    row.produced_entity_type = produced_entity_type
    row.produced_entity_id = produced_entity_id
    row.produced_entity_count = produced_entity_count
    row.last_processing_result = last_processing_result
    row.replay_required = replay_required
    row.replay_reason = replay_reason
    row.last_attempted_at = now
    if processing_status == STATUS_COMPLETE and not replay_required:
        row.processed_at = now
    db.commit()
    db.refresh(row)
    return row


def mark_replay_required(db: Session, message_id: str, reason: str) -> None:
    upsert_processing_record(
        db,
        message_id,
        processing_status=STATUS_REPLAY_REQUIRED,
        replay_required=True,
        replay_reason=reason,
    )


def record_processing_outcome(
    db: Session,
    message_id: str,
    *,
    message_type: str,
    jobs_created: int = 0,
    job_ids: list[int] | None = None,
    signal_id: int | None = None,
    result_summary: dict | None = None,
    failed: bool = False,
    replay_reason: str | None = None,
) -> ProcessedGmailMessage:
    if failed:
        return upsert_processing_record(
            db,
            message_id,
            message_type=message_type,
            parser_version=GMAIL_PARSER_VERSION,
            processing_status=STATUS_FAILED,
            produced_entity_type=ENTITY_NONE,
            produced_entity_count=0,
            last_processing_result=json.dumps(result_summary or {}),
            replay_required=True,
            replay_reason=replay_reason or "processing failed",
        )
    if message_type == "JOB_ALERT":
        entity_type = ENTITY_JOB if jobs_created else ENTITY_NONE
        entity_id = str(job_ids[0]) if job_ids else None
        needs_replay = jobs_created == 0
        return upsert_processing_record(
            db,
            message_id,
            message_type=message_type,
            parser_version=GMAIL_PARSER_VERSION,
            processing_status=STATUS_REPLAY_REQUIRED if needs_replay else STATUS_COMPLETE,
            produced_entity_type=entity_type,
            produced_entity_id=entity_id,
            produced_entity_count=jobs_created,
            last_processing_result=json.dumps(result_summary or {"jobs_created": jobs_created}),
            replay_required=needs_replay,
            replay_reason=replay_reason if needs_replay else None,
        )
    return upsert_processing_record(
        db,
        message_id,
        message_type=message_type,
        parser_version=GMAIL_PARSER_VERSION,
        processing_status=STATUS_COMPLETE,
        produced_entity_type=ENTITY_RECRUITER_SIGNAL if signal_id else ENTITY_NONE,
        produced_entity_id=str(signal_id) if signal_id else None,
        produced_entity_count=1 if signal_id else 0,
        last_processing_result=json.dumps(result_summary or {}),
        replay_required=False,
    )


def backfill_legacy_rows(db: Session) -> dict:
    """Mark legacy imported rows for replay when they suppress job recovery."""
    updated = 0
    for row in db.query(ProcessedGmailMessage).filter(
        ProcessedGmailMessage.processing_status == STATUS_LEGACY
    ).all():
        needs, reason = _legacy_row_needs_replay(row, db)
        if needs:
            row.processing_status = STATUS_REPLAY_REQUIRED
            row.replay_required = True
            row.replay_reason = reason
            row.parser_version = row.parser_version or "1.0.0"
            row.message_type = row.message_type or "JOB_ALERT"
            row.last_attempted_at = row.processed_at
            db.add(row)
            updated += 1
    db.commit()
    return {"legacy_rows_updated": updated}
