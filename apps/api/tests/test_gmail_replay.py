"""Tests for Gmail replay semantics."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ProcessedGmailMessage, RecruiterSignal
from app.services.gmail_replay import (
    GMAIL_PARSER_VERSION,
    backfill_legacy_rows,
    classify_processed_row,
    record_processing_outcome,
    should_replay_row,
    should_skip_gmail_fetch,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_legacy_processed_without_job_requires_replay(db):
    row = ProcessedGmailMessage(message_id="msg-legacy-1", processed_at=datetime.utcnow())
    db.add(row)
    db.commit()
    replay, reason = should_replay_row(row, db)
    assert replay is True
    assert "without surviving" in reason


def test_complete_job_alert_with_output_skips_fetch(db):
    row = ProcessedGmailMessage(
        message_id="msg-complete-1",
        processed_at=datetime.utcnow(),
        message_type="JOB_ALERT",
        parser_version=GMAIL_PARSER_VERSION,
        processing_status="COMPLETE",
        produced_entity_type="job",
        produced_entity_count=1,
        replay_required=False,
    )
    db.add(row)
    db.commit()
    assert should_skip_gmail_fetch(row, db) is True


def test_replay_required_does_not_skip_fetch(db):
    row = ProcessedGmailMessage(
        message_id="msg-replay-1",
        processed_at=datetime.utcnow(),
        message_type="JOB_ALERT",
        processing_status="REPLAY_REQUIRED",
        replay_required=True,
        replay_reason="no output",
    )
    db.add(row)
    db.commit()
    assert should_skip_gmail_fetch(row, db) is False


def test_record_processing_outcome_job_alert_zero_output(db):
    record_processing_outcome(
        db,
        "msg-out-1",
        message_type="JOB_ALERT",
        jobs_created=0,
        result_summary={"reason": "rejected"},
    )
    row = db.query(ProcessedGmailMessage).filter_by(message_id="msg-out-1").one()
    assert row.replay_required is True
    assert row.produced_entity_count == 0


def test_classify_non_job_lifecycle_signal(db):
    row = ProcessedGmailMessage(message_id="msg-interview-1", processed_at=datetime.utcnow())
    db.add(row)
    db.add(
        RecruiterSignal(
            source="gmail",
            body_text="interview",
            signal_type="INTERVIEW",
            gmail_message_id="msg-interview-1",
        )
    )
    db.commit()
    result = classify_processed_row(row, db)
    assert result["classification"] == "NON_JOB_LIFECYCLE"


def test_backfill_legacy_marks_replay(db):
    row = ProcessedGmailMessage(message_id="msg-backfill-1", processed_at=datetime.utcnow())
    db.add(row)
    db.commit()
    summary = backfill_legacy_rows(db)
    assert summary["legacy_rows_updated"] >= 1
    db.refresh(row)
    assert row.replay_required is True
