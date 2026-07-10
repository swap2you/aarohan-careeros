"""Phase 3 row-level recovery classification for owner candidate build."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

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
    ValidationRun,
)
from app.services.legacy_data_inventory import (
    E2E_ACTOR_EMAIL,
    classify_application,
    classify_company,
    classify_job,
    _e2e_actor_job_ids,
    _fixture_audit_job_ids,
)
from app.services.provenance import PROVENANCE_FIXTURE, PROVENANCE_MANUAL, PROVENANCE_TEST

CLASS_OWNER_CONFIRMED = "OWNER_CONFIRMED"
CLASS_LIVE_RECONSTRUCT = "LIVE_SOURCE_RECONSTRUCTABLE"
CLASS_SYSTEM_REQUIRED = "SYSTEM_REQUIRED"
CLASS_TEST = "TEST"
CLASS_FIXTURE = "FIXTURE"
CLASS_AMBIGUOUS = "AMBIGUOUS"
CLASS_EXCLUDE = "EXCLUDE"

GMAIL_JOB_SOURCES = {
    "linkedin_alert_emails",
    "indeed_alert_emails",
    "dice_alert_emails",
    "usajobs_alert_emails",
    "glassdoor_alert_emails",
}
CONNECTOR_SOURCES = {
    "greenhouse_public_get",
    "lever_public_get",
    "remote_ok_public_get",
    "jooble_api",
    "adzuna_api",
    "usajobs_api",
    "rss",
    "approved_remote_feeds",
}
PG_TEST_MARKERS = ("PG Test Co",)
EXAMPLE_MARKERS = ("Example Health Tech", "Department of Example")
E2E_EMAIL = "e2e@test.local"


@dataclass
class RecoveryClassification:
    table: str
    record_id: int
    classification: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    linked_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_pg_test(name: str) -> bool:
    return any(marker in (name or "") for marker in PG_TEST_MARKERS)


def _is_example_fixture(name: str) -> bool:
    return any(marker in (name or "") for marker in EXAMPLE_MARKERS)


def _legacy_to_recovery(legacy) -> RecoveryClassification | None:
    if legacy is None:
        return None
    if legacy.proposed_provenance == PROVENANCE_TEST:
        cls = CLASS_TEST
    elif legacy.proposed_provenance == PROVENANCE_FIXTURE:
        cls = CLASS_FIXTURE
    else:
        cls = CLASS_EXCLUDE
    return RecoveryClassification(
        table=legacy.table,
        record_id=legacy.record_id,
        classification=cls,
        reason=legacy.proposed_action,
        evidence=list(legacy.evidence),
        linked_ids=list(legacy.linked_children),
    )


def classify_user(user: User) -> RecoveryClassification:
    if (user.email or "").lower() == E2E_EMAIL:
        return RecoveryClassification(
            table="users",
            record_id=user.id,
            classification=CLASS_EXCLUDE,
            reason="E2E test account",
            evidence=[f"email={user.email!r}"],
        )
    return RecoveryClassification(
        table="users",
        record_id=user.id,
        classification=CLASS_SYSTEM_REQUIRED,
        reason="owner admin account",
        evidence=[f"email={user.email!r}", f"is_admin={user.is_admin}"],
    )


def classify_job_row(
    job: Job,
    *,
    e2e_actor_ids: set[int],
    fixture_audit_ids: set[int],
    application_job_ids: set[int],
) -> RecoveryClassification:
    legacy = classify_job(job, e2e_actor_ids=e2e_actor_ids, fixture_audit_ids=fixture_audit_ids)
    converted = _legacy_to_recovery(legacy)
    if converted:
        return converted

    company = job.company or ""
    source = (job.source or "").lower()
    title = job.title or ""

    if _is_pg_test(company):
        return RecoveryClassification(
            table="jobs",
            record_id=job.id,
            classification=CLASS_EXCLUDE,
            reason="PG Test Co synthetic record",
            evidence=[f"company={company!r}"],
        )
    if _is_example_fixture(company):
        return RecoveryClassification(
            table="jobs",
            record_id=job.id,
            classification=CLASS_FIXTURE,
            reason="Example/fixture company",
            evidence=[f"company={company!r}"],
        )
    if company.startswith("E2E ") or company.startswith("E2E GH"):
        return RecoveryClassification(
            table="jobs",
            record_id=job.id,
            classification=CLASS_TEST,
            reason="E2E company prefix",
            evidence=[f"company={company!r}"],
        )
    if "gitlab" in company.lower() and source in CONNECTOR_SOURCES:
        return RecoveryClassification(
            table="jobs",
            record_id=job.id,
            classification=CLASS_EXCLUDE,
            reason="GitLab board flood candidate",
            evidence=[f"company={company!r}", f"source={source!r}"],
        )
    if "digest" in title.lower() and len(title.split()) <= 4:
        return RecoveryClassification(
            table="jobs",
            record_id=job.id,
            classification=CLASS_EXCLUDE,
            reason="Malformed digest title",
            evidence=[f"title={title!r}"],
        )

    if job.id in application_job_ids or source in {PROVENANCE_MANUAL, "manual", "url_import", "forwarded"}:
        return RecoveryClassification(
            table="jobs",
            record_id=job.id,
            classification=CLASS_OWNER_CONFIRMED,
            reason="linked application or manual opportunity",
            evidence=[f"source={source!r}", f"has_application={job.id in application_job_ids}"],
        )
    if source in GMAIL_JOB_SOURCES or source.endswith("_alert_emails"):
        return RecoveryClassification(
            table="jobs",
            record_id=job.id,
            classification=CLASS_LIVE_RECONSTRUCT,
            reason="Gmail alert source — reconstruct with current eligibility",
            evidence=[f"source={source!r}"],
        )
    if source in CONNECTOR_SOURCES:
        return RecoveryClassification(
            table="jobs",
            record_id=job.id,
            classification=CLASS_LIVE_RECONSTRUCT,
            reason="connector/API source — reconstruct with current eligibility",
            evidence=[f"source={source!r}"],
        )
    if getattr(job, "data_provenance", None) in {PROVENANCE_FIXTURE, PROVENANCE_TEST}:
        return RecoveryClassification(
            table="jobs",
            record_id=job.id,
            classification=CLASS_EXCLUDE,
            reason="tagged fixture/test provenance",
            evidence=[f"data_provenance={job.data_provenance!r}"],
        )

    return RecoveryClassification(
        table="jobs",
        record_id=job.id,
        classification=CLASS_AMBIGUOUS,
        reason="insufficient provenance to auto-import",
        evidence=[f"source={source!r}", f"company={company!r}"],
    )


def build_recovery_classification(db: Session) -> dict[str, Any]:
    e2e_actor_ids = _e2e_actor_job_ids(db)
    fixture_audit_ids = _fixture_audit_job_ids(db)
    application_job_ids = {row.job_id for row in db.query(Application.job_id).all()}

    rows: list[RecoveryClassification] = []
    job_class: dict[int, RecoveryClassification] = {}

    for user in db.query(User).order_by(User.id):
        rows.append(classify_user(user))

    for job in db.query(Job).order_by(Job.id):
        c = classify_job_row(
            job,
            e2e_actor_ids=e2e_actor_ids,
            fixture_audit_ids=fixture_audit_ids,
            application_job_ids=application_job_ids,
        )
        job_class[job.id] = c
        rows.append(c)

    for company in db.query(Company).order_by(Company.id):
        legacy = classify_company(db, company)
        if legacy:
            rows.append(_legacy_to_recovery(legacy) or RecoveryClassification(
                table="companies", record_id=company.id, classification=CLASS_EXCLUDE,
                reason="fixture/test company", evidence=legacy.evidence,
            ))
            continue
        linked_jobs = db.query(Job).filter(Job.company_id == company.id).all()
        classes = {job_class[j.id].classification for j in linked_jobs if j.id in job_class}
        if not linked_jobs:
            rows.append(RecoveryClassification(
                table="companies", record_id=company.id, classification=CLASS_AMBIGUOUS,
                reason="orphan company", evidence=["no linked jobs"],
            ))
        elif classes <= {CLASS_OWNER_CONFIRMED, CLASS_SYSTEM_REQUIRED}:
            rows.append(RecoveryClassification(
                table="companies", record_id=company.id, classification=CLASS_OWNER_CONFIRMED,
                reason="linked to owner-confirmed jobs", evidence=[f"job_classes={sorted(classes)}"],
            ))
        elif CLASS_LIVE_RECONSTRUCT in classes:
            rows.append(RecoveryClassification(
                table="companies", record_id=company.id, classification=CLASS_LIVE_RECONSTRUCT,
                reason="linked to reconstructable jobs", evidence=[f"job_classes={sorted(classes)}"],
            ))
        elif classes <= {CLASS_EXCLUDE, CLASS_TEST, CLASS_FIXTURE}:
            rows.append(RecoveryClassification(
                table="companies", record_id=company.id, classification=CLASS_EXCLUDE,
                reason="only excluded/test jobs", evidence=[f"job_classes={sorted(classes)}"],
            ))
        else:
            rows.append(RecoveryClassification(
                table="companies", record_id=company.id, classification=CLASS_AMBIGUOUS,
                reason="mixed job classifications", evidence=[f"job_classes={sorted(classes)}"],
            ))

    for app in db.query(Application).order_by(Application.id):
        job = db.query(Job).filter(Job.id == app.job_id).one_or_none()
        jc = job_class.get(app.job_id)
        if jc and jc.classification in {CLASS_EXCLUDE, CLASS_TEST, CLASS_FIXTURE}:
            rows.append(RecoveryClassification(
                table="applications", record_id=app.id, classification=CLASS_EXCLUDE,
                reason=f"linked job classified {jc.classification}",
                evidence=jc.evidence, linked_ids=[f"job:{app.job_id}"],
            ))
        elif jc and jc.classification == CLASS_OWNER_CONFIRMED:
            rows.append(RecoveryClassification(
                table="applications", record_id=app.id, classification=CLASS_OWNER_CONFIRMED,
                reason="owner application workflow", evidence=[f"job_id={app.job_id}"],
            ))
        else:
            legacy = classify_application(app, job)
            if legacy:
                rows.append(_legacy_to_recovery(legacy) or RecoveryClassification(
                    table="applications", record_id=app.id, classification=CLASS_EXCLUDE,
                    reason="fixture/test application", evidence=legacy.evidence,
                ))
            else:
                rows.append(RecoveryClassification(
                    table="applications", record_id=app.id, classification=CLASS_AMBIGUOUS,
                    reason="application without confirmed owner job",
                    evidence=[f"job_id={app.job_id}"],
                ))

    for model, table, default_class in (
        (ApplicationDocumentVersion, "application_document_versions", CLASS_OWNER_CONFIRMED),
        (ApplicationTimelineEvent, "application_timeline_events", CLASS_OWNER_CONFIRMED),
        (ApprovalAction, "approval_actions", CLASS_OWNER_CONFIRMED),
        (ApplicationLedger, "application_ledger", CLASS_OWNER_CONFIRMED),
        (ApplicationEvent, "application_events", CLASS_OWNER_CONFIRMED),
        (JobScore, "job_scores", CLASS_LIVE_RECONSTRUCT),
        (InterviewPack, "interview_packs", CLASS_OWNER_CONFIRMED),
        (RepresentationRecord, "representation_records", CLASS_OWNER_CONFIRMED),
    ):
        for row in db.query(model).order_by(model.id):
            parent_class = _parent_class(db, row, job_class)
            cls = parent_class or default_class
            if cls in {CLASS_EXCLUDE, CLASS_TEST, CLASS_FIXTURE, CLASS_AMBIGUOUS} and table != "job_scores":
                if cls == CLASS_AMBIGUOUS:
                    cls = CLASS_EXCLUDE
            rows.append(RecoveryClassification(
                table=table, record_id=row.id, classification=cls,
                reason=f"derived from parent records", evidence=[f"parent_class={parent_class}"],
            ))

    for token in db.query(OAuthToken).order_by(OAuthToken.id):
        email = (token.account_email or "").lower()
        if E2E_EMAIL in email or "test" in email:
            rows.append(RecoveryClassification(
                table="oauth_tokens", record_id=token.id, classification=CLASS_EXCLUDE,
                reason="test OAuth account", evidence=[f"account_email={token.account_email!r}"],
            ))
        else:
            rows.append(RecoveryClassification(
                table="oauth_tokens", record_id=token.id, classification=CLASS_OWNER_CONFIRMED,
                reason="owner Google OAuth metadata", evidence=[f"provider={token.provider!r}"],
            ))

    for msg in db.query(ProcessedGmailMessage).order_by(ProcessedGmailMessage.id):
        if (msg.message_id or "").startswith("fixture-"):
            rows.append(RecoveryClassification(
                table="processed_gmail_messages", record_id=msg.id, classification=CLASS_EXCLUDE,
                reason="fixture gmail id", evidence=[f"message_id={msg.message_id!r}"],
            ))
        else:
            rows.append(RecoveryClassification(
                table="processed_gmail_messages", record_id=msg.id, classification=CLASS_OWNER_CONFIRMED,
                reason="owner gmail idempotency record", evidence=[f"message_id={msg.message_id!r}"],
            ))

    for review in db.query(GmailIngestReview).order_by(GmailIngestReview.id):
        if review.status == "quarantined":
            rows.append(RecoveryClassification(
                table="gmail_ingest_reviews", record_id=review.id, classification=CLASS_EXCLUDE,
                reason="quarantined gmail ingest", evidence=[review.ignored_reason or "quarantined"],
            ))
        elif review.job_id and job_class.get(review.job_id, RecoveryClassification("", 0, CLASS_AMBIGUOUS, "")).classification in {
            CLASS_EXCLUDE, CLASS_TEST, CLASS_FIXTURE
        }:
            rows.append(RecoveryClassification(
                table="gmail_ingest_reviews", record_id=review.id, classification=CLASS_EXCLUDE,
                reason="linked excluded job", evidence=[f"job_id={review.job_id}"],
            ))
        else:
            rows.append(RecoveryClassification(
                table="gmail_ingest_reviews", record_id=review.id, classification=CLASS_AMBIGUOUS,
                reason="gmail review requires manual review", evidence=[f"status={review.status!r}"],
            ))

    for signal in db.query(RecruiterSignal).order_by(RecruiterSignal.id):
        jc = job_class.get(signal.job_id) if signal.job_id else None
        cls = jc.classification if jc else CLASS_OWNER_CONFIRMED
        if cls in {CLASS_EXCLUDE, CLASS_TEST, CLASS_FIXTURE}:
            cls = CLASS_EXCLUDE
        rows.append(RecoveryClassification(
            table="recruiter_signals", record_id=signal.id, classification=cls,
            reason="recruiter signal", evidence=[f"job_id={signal.job_id}"],
        ))

    for audit in db.query(AuditLog).order_by(AuditLog.id):
        if audit.actor == E2E_ACTOR_EMAIL:
            rows.append(RecoveryClassification(
                table="audit_logs", record_id=audit.id, classification=CLASS_EXCLUDE,
                reason="E2E audit actor", evidence=[f"event_type={audit.event_type!r}"],
            ))
        elif audit.event_type in {"workflow.ingest_fixture", "connector.fixture"}:
            rows.append(RecoveryClassification(
                table="audit_logs", record_id=audit.id, classification=CLASS_EXCLUDE,
                reason="fixture workflow audit", evidence=[f"event_type={audit.event_type!r}"],
            ))
        else:
            rows.append(RecoveryClassification(
                table="audit_logs", record_id=audit.id, classification=CLASS_OWNER_CONFIRMED,
                reason="owner audit trail", evidence=[f"event_type={audit.event_type!r}"],
            ))

    for run in db.query(ConnectorRun).order_by(ConnectorRun.id):
        if not run.live or (run.actor or "").lower() == E2E_EMAIL:
            rows.append(RecoveryClassification(
                table="connector_runs", record_id=run.id, classification=CLASS_EXCLUDE,
                reason="non-live or test connector run",
                evidence=[f"live={run.live}", f"actor={run.actor!r}"],
            ))
        else:
            rows.append(RecoveryClassification(
                table="connector_runs", record_id=run.id, classification=CLASS_OWNER_CONFIRMED,
                reason="owner connector history", evidence=[f"provider={run.provider!r}"],
            ))

    for usage in db.query(AIUsageRecord).order_by(AIUsageRecord.id):
        jc = job_class.get(usage.job_id) if usage.job_id else None
        if jc and jc.classification in {CLASS_EXCLUDE, CLASS_TEST, CLASS_FIXTURE}:
            rows.append(RecoveryClassification(
                table="ai_usage_records", record_id=usage.id, classification=CLASS_EXCLUDE,
                reason="AI usage on excluded job", evidence=[f"job_id={usage.job_id}"],
            ))
        else:
            rows.append(RecoveryClassification(
                table="ai_usage_records", record_id=usage.id, classification=CLASS_OWNER_CONFIRMED,
                reason="owner AI usage", evidence=[f"operation={usage.operation!r}"],
            ))

    for setting in db.query(SystemSetting).order_by(SystemSetting.id):
        rows.append(RecoveryClassification(
            table="system_settings", record_id=setting.id, classification=CLASS_SYSTEM_REQUIRED,
            reason="owner configuration", evidence=[f"key={setting.key!r}"],
        ))

    for run in db.query(ValidationRun).order_by(ValidationRun.id):
        rows.append(RecoveryClassification(
            table="validation_runs", record_id=run.id, classification=CLASS_EXCLUDE,
            reason="validation infrastructure artifact", evidence=[f"status={run.status!r}"],
        ))

    summary: dict[str, int] = {}
    for row in rows:
        summary[row.classification] = summary.get(row.classification, 0) + 1

    recovery_rows = [r for r in rows if r.classification not in {CLASS_EXCLUDE, CLASS_TEST, CLASS_FIXTURE, CLASS_AMBIGUOUS}]
    exclusion_rows = [r for r in rows if r.classification in {CLASS_EXCLUDE, CLASS_TEST, CLASS_FIXTURE}]
    ambiguous_rows = [r for r in rows if r.classification == CLASS_AMBIGUOUS]

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary_by_classification": summary,
        "recovery_manifest": [r.to_dict() for r in recovery_rows],
        "exclusion_manifest": [r.to_dict() for r in exclusion_rows],
        "ambiguous_rows": [r.to_dict() for r in ambiguous_rows],
        "total_rows": len(rows),
    }


def _parent_class(db: Session, row: Any, job_class: dict[int, RecoveryClassification]) -> str | None:
    job_id = getattr(row, "job_id", None)
    if job_id and job_id in job_class:
        return job_class[job_id].classification
    app_id = getattr(row, "application_id", None)
    if app_id:
        app = db.query(Application).filter(Application.id == app_id).one_or_none()
        if app and app.job_id in job_class:
            return job_class[app.job_id].classification
    return None
