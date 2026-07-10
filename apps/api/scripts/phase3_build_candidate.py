#!/usr/bin/env python3
"""Import classified recovery rows into a fresh owner candidate database."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AIUsageRecord,
    Application,
    ApplicationDocumentVersion,
    ApplicationEvent,
    ApplicationLedger,
    ApplicationTimelineEvent,
    ApprovalAction,
    AuditLog,
    Company,
    CompanyAlias,
    CompanyAtsIdentity,
    CompanyDomain,
    ConnectorRun,
    GmailIngestReview,
    InterviewPack,
    Job,
    JobScore,
    OAuthToken,
    ProcessedGmailMessage,
    RecruiterSignal,
    RepresentationRecord,
    SystemSetting,
    User,
)
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity
from app.services.recovery_row_classification import (
    CLASS_LIVE_RECONSTRUCT,
    CLASS_OWNER_CONFIRMED,
    CLASS_SYSTEM_REQUIRED,
)


def _load_ids(manifest: dict[str, Any], table: str, classes: set[str]) -> set[int]:
    return {
        int(row["record_id"])
        for row in manifest.get("rows", [])
        if row.get("table") == table and row.get("classification") in classes
    }


def _copy_table(source: Session, target: Session, model, ids: set[int]) -> int:
    if not ids:
        return 0
    rows = source.query(model).filter(model.id.in_(ids)).all()
    copied = 0
    for row in rows:
        data = {col.name: getattr(row, col.name) for col in model.__table__.columns}
        target.execute(model.__table__.insert().values(**data))
        copied += 1
    target.commit()
    return copied


def _reset_sequences(target: Session) -> None:
    for table in target.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND column_name = 'id'
              AND column_default LIKE 'nextval%'
            """
        )
    ).fetchall():
        table_name = table[0]
        target.execute(
            text(
                f"""
                SELECT setval(
                  pg_get_serial_sequence('public.{table_name}', 'id'),
                  COALESCE((SELECT MAX(id) FROM public.{table_name}), 1),
                  (SELECT COUNT(*) > 0 FROM public.{table_name})
                )
                """
            )
        )
    target.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 3 owner candidate import")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--recovery-manifest", required=True)
    parser.add_argument("--reconstruction-json", required=True)
    args = parser.parse_args(argv)

    os.environ["AAROHAN_DB_IDENTITY_PURPOSE"] = os.environ.get("AAROHAN_DB_IDENTITY_PURPOSE", "OWNER_CANDIDATE")
    validate_recovery_database_identity(database_url=args.target_url)

    recovery_manifest = json.loads(open(args.recovery_manifest, encoding="utf-8").read())
    reconstruction = json.loads(open(args.reconstruction_json, encoding="utf-8").read())
    import_job_ids = set(reconstruction.get("import_job_ids") or [])

    confirmed = {CLASS_OWNER_CONFIRMED, CLASS_SYSTEM_REQUIRED}
    user_ids = _load_ids(recovery_manifest, "users", confirmed)
    setting_ids = _load_ids(recovery_manifest, "system_settings", confirmed)
    oauth_ids = _load_ids(recovery_manifest, "oauth_tokens", confirmed)
    owner_job_ids = _load_ids(recovery_manifest, "jobs", {CLASS_OWNER_CONFIRMED})
    job_ids = owner_job_ids | import_job_ids
    company_ids = _load_ids(recovery_manifest, "companies", {CLASS_OWNER_CONFIRMED, CLASS_LIVE_RECONSTRUCT})
    application_ids = _load_ids(recovery_manifest, "applications", {CLASS_OWNER_CONFIRMED})
    doc_version_ids = _load_ids(recovery_manifest, "application_document_versions", {CLASS_OWNER_CONFIRMED})
    timeline_ids = _load_ids(recovery_manifest, "application_timeline_events", {CLASS_OWNER_CONFIRMED})
    approval_ids = _load_ids(recovery_manifest, "approval_actions", {CLASS_OWNER_CONFIRMED})
    ledger_ids = _load_ids(recovery_manifest, "application_ledger", {CLASS_OWNER_CONFIRMED})
    event_ids = _load_ids(recovery_manifest, "application_events", {CLASS_OWNER_CONFIRMED})
    gmail_ids = _load_ids(recovery_manifest, "processed_gmail_messages", {CLASS_OWNER_CONFIRMED})
    review_ids = _load_ids(recovery_manifest, "gmail_ingest_reviews", {CLASS_OWNER_CONFIRMED})
    signal_ids = _load_ids(recovery_manifest, "recruiter_signals", {CLASS_OWNER_CONFIRMED, CLASS_LIVE_RECONSTRUCT})
    interview_ids = _load_ids(recovery_manifest, "interview_packs", {CLASS_OWNER_CONFIRMED})
    audit_ids = _load_ids(recovery_manifest, "audit_logs", {CLASS_OWNER_CONFIRMED})
    ai_ids = _load_ids(recovery_manifest, "ai_usage_records", {CLASS_OWNER_CONFIRMED})
    connector_ids = _load_ids(recovery_manifest, "connector_runs", {CLASS_OWNER_CONFIRMED})
    representation_ids = _load_ids(recovery_manifest, "representation_records", {CLASS_OWNER_CONFIRMED})

    source_engine = create_engine(args.source_url)
    target_engine = create_engine(args.target_url)
    Source = sessionmaker(bind=source_engine)
    Target = sessionmaker(bind=target_engine)
    source = Source()
    target = Target()

    counts: dict[str, int] = {}
    try:
        if not job_ids:
            company_ids = set()
        elif job_ids:
            linked_company_ids = {
                cid
                for (cid,) in source.query(Job.company_id)
                .filter(Job.id.in_(job_ids), Job.company_id.isnot(None))
                .all()
                if cid
            }
            company_ids &= linked_company_ids | _load_ids(recovery_manifest, "companies", {CLASS_OWNER_CONFIRMED})

        if application_ids:
            application_ids = {
                row.id
                for row in source.query(Application).filter(
                    Application.id.in_(application_ids),
                    Application.job_id.in_(job_ids),
                ).all()
            }
        else:
            ledger_ids = set()
            event_ids = set()

        if ledger_ids and application_ids:
            ledger_ids = {
                row.id
                for row in source.query(ApplicationLedger).filter(ApplicationLedger.id.in_(ledger_ids)).all()
                if (row.application_id is None or row.application_id in application_ids)
                and (row.job_id is None or row.job_id in job_ids)
            }
        else:
            ledger_ids = set()

        event_ids = {
            row.id
            for row in source.query(ApplicationEvent).filter(ApplicationEvent.ledger_id.in_(ledger_ids)).all()
            if (row.actor_email or "").lower() not in {"e2e@test.local", "pg@test.local"}
        } if ledger_ids else set()

        if application_ids:
            doc_version_ids = {
                row.id
                for row in source.query(ApplicationDocumentVersion)
                .filter(ApplicationDocumentVersion.application_id.in_(application_ids))
                .all()
            }
            timeline_ids = {
                row.id
                for row in source.query(ApplicationTimelineEvent)
                .filter(ApplicationTimelineEvent.application_id.in_(application_ids))
                .all()
            }
            approval_ids = {
                row.id
                for row in source.query(ApprovalAction)
                .filter(ApprovalAction.application_id.in_(application_ids))
                .all()
            }
        else:
            doc_version_ids = set()
            timeline_ids = set()
            approval_ids = set()

        counts["users"] = _copy_table(source, target, User, user_ids)
        counts["system_settings"] = _copy_table(source, target, SystemSetting, setting_ids)
        if oauth_ids:
            seen_oauth: set[tuple[str, str, str]] = set()
            deduped_oauth_ids: set[int] = set()
            for token in (
                source.query(OAuthToken)
                .filter(OAuthToken.id.in_(oauth_ids))
                .order_by(OAuthToken.id.desc())
                .all()
            ):
                key = (
                    (token.provider or "").lower(),
                    (token.service or "").lower(),
                    (token.account_email or "").lower(),
                )
                if key in seen_oauth:
                    continue
                seen_oauth.add(key)
                deduped_oauth_ids.add(token.id)
            oauth_ids = deduped_oauth_ids
        counts["oauth_tokens"] = _copy_table(source, target, OAuthToken, oauth_ids)
        counts["companies"] = _copy_table(source, target, Company, company_ids)
        if company_ids:
            alias_ids = {
                row.id
                for row in source.query(CompanyAlias).filter(CompanyAlias.company_id.in_(company_ids)).all()
            }
            domain_ids = {
                row.id
                for row in source.query(CompanyDomain).filter(CompanyDomain.company_id.in_(company_ids)).all()
            }
            ats_ids = {
                row.id
                for row in source.query(CompanyAtsIdentity).filter(CompanyAtsIdentity.company_id.in_(company_ids)).all()
            }
            counts["company_aliases"] = _copy_table(source, target, CompanyAlias, alias_ids)
            counts["company_domains"] = _copy_table(source, target, CompanyDomain, domain_ids)
            counts["company_ats_identities"] = _copy_table(source, target, CompanyAtsIdentity, ats_ids)
        counts["jobs"] = _copy_table(source, target, Job, job_ids)
        score_ids: set[int] = set()
        if job_ids:
            score_ids = {row.id for row in source.query(JobScore).filter(JobScore.job_id.in_(job_ids)).all()}
        counts["job_scores"] = _copy_table(source, target, JobScore, score_ids)

        signal_ids = {
            row.id
            for row in source.query(RecruiterSignal).filter(RecruiterSignal.id.in_(signal_ids)).all()
            if (row.job_id is None or row.job_id in job_ids)
            and (row.application_id is None or row.application_id in application_ids)
            and not (row.gmail_message_id or "").startswith("fixture-")
            and (row.source or "") != "gmail_fixture"
        }
        ai_ids = {
            row.id
            for row in source.query(AIUsageRecord).filter(AIUsageRecord.id.in_(ai_ids)).all()
            if row.job_id is None or row.job_id in job_ids
        }
        interview_ids = {
            row.id
            for row in source.query(InterviewPack).filter(InterviewPack.id.in_(interview_ids)).all()
            if row.job_id in job_ids
        }
        counts["applications"] = _copy_table(source, target, Application, application_ids)
        counts["application_document_versions"] = _copy_table(source, target, ApplicationDocumentVersion, doc_version_ids)
        counts["application_timeline_events"] = _copy_table(source, target, ApplicationTimelineEvent, timeline_ids)
        counts["approval_actions"] = _copy_table(source, target, ApprovalAction, approval_ids)
        counts["application_ledger"] = _copy_table(source, target, ApplicationLedger, ledger_ids)
        counts["application_events"] = _copy_table(source, target, ApplicationEvent, event_ids)
        counts["processed_gmail_messages"] = _copy_table(source, target, ProcessedGmailMessage, gmail_ids)
        counts["gmail_ingest_reviews"] = _copy_table(source, target, GmailIngestReview, review_ids)
        counts["recruiter_signals"] = _copy_table(source, target, RecruiterSignal, signal_ids)
        counts["interview_packs"] = _copy_table(source, target, InterviewPack, interview_ids)
        counts["audit_logs"] = _copy_table(source, target, AuditLog, audit_ids)
        counts["ai_usage_records"] = _copy_table(source, target, AIUsageRecord, ai_ids)
        counts["connector_runs"] = _copy_table(source, target, ConnectorRun, connector_ids)
        counts["representation_records"] = _copy_table(source, target, RepresentationRecord, representation_ids)
        _reset_sequences(target)
    finally:
        source.close()
        target.close()
        source_engine.dispose()
        target_engine.dispose()

    print(json.dumps({"imported_counts": counts, "import_job_ids": sorted(job_ids)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
