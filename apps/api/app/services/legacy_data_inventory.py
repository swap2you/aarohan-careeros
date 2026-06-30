"""Defensible classification of legacy fixture/test records for owner cleanup."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Application,
    ApplicationDocumentVersion,
    ApplicationTimelineEvent,
    AuditLog,
    Company,
    GmailIngestReview,
    Job,
    ProcessedGmailMessage,
    RecruiterSignal,
)
from app.services.provenance import (
    FIXTURE_SOURCES,
    PROVENANCE_FIXTURE,
    PROVENANCE_GMAIL,
    PROVENANCE_TEST,
    infer_provenance,
)

E2E_ACTOR_EMAIL = "e2e@test.local"
FIXTURE_EXTERNAL_IDS = frozenset({"fixture-remote-qe-001"})
E2E_EXTERNAL_PREFIXES = ("e2e-", "e2e_")
E2E_URL_MARKERS = ("/e2e/", "example.com/e2e")
E2E_REQUISITION_PREFIX = "REQ-E2E-"
GMAIL_LOW_CONFIDENCE = 0.72

# Compound naming: E2E prefix alone is insufficient; requires corroborating signal.
E2E_NAME_PREFIXES = ("E2E ", "E2E GH", "Example Health Tech")


@dataclass
class Classification:
    table: str
    record_id: int
    display_name: str
    current_provenance: str
    proposed_provenance: str
    proposed_action: str  # tag_fixture | tag_test | tag_gmail_invalid | delete_candidate | preserve
    evidence: list[str] = field(default_factory=list)
    linked_children: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)


def _job_fixture_source(job: Job) -> bool:
    src = (job.source or "").lower()
    if src in FIXTURE_SOURCES or "fixture" in src:
        return True
    if job.external_id in FIXTURE_EXTERNAL_IDS:
        return True
    if (job.external_id or "").lower().startswith("fixture-"):
        return True
    return False


def _job_e2e_external(job: Job) -> bool:
    ext = (job.external_id or "").lower()
    return ext.startswith(E2E_EXTERNAL_PREFIXES)


def _job_e2e_url(job: Job) -> bool:
    url = (job.url or "").lower()
    return any(marker in url for marker in E2E_URL_MARKERS)


def _job_e2e_requisition(job: Job) -> bool:
    req = job.requisition_id or ""
    return req.startswith(E2E_REQUISITION_PREFIX)


def _job_e2e_name_with_corroboration(job: Job) -> bool:
    company = job.company or ""
    if not any(company.startswith(p) or company == p for p in E2E_NAME_PREFIXES):
        return False
    return _job_e2e_external(job) or _job_e2e_url(job) or _job_e2e_requisition(job)


def _e2e_actor_job_ids(db: Session) -> set[int]:
    rows = (
        db.query(AuditLog.resource_id)
        .filter(
            AuditLog.actor == E2E_ACTOR_EMAIL,
            AuditLog.event_type.in_(("job.ingested", "job.updated", "packet.generated")),
            AuditLog.resource_type == "job",
        )
        .all()
    )
    ids: set[int] = set()
    for (rid,) in rows:
        if rid and str(rid).isdigit():
            ids.add(int(rid))
    return ids


def _fixture_audit_job_ids(db: Session) -> set[int]:
    rows = db.query(AuditLog.details).filter(AuditLog.event_type == "workflow.ingest_fixture").all()
    ids: set[int] = set()
    for (details,) in rows:
        if not isinstance(details, dict):
            continue
        for item in details.get("jobs") or details.get("ingested") or []:
            if isinstance(item, dict) and item.get("id"):
                ids.add(int(item["id"]))
            elif isinstance(item, int):
                ids.add(item)
        for jid in details.get("job_ids") or []:
            ids.add(int(jid))
    return ids


def classify_job(
    job: Job,
    *,
    e2e_actor_ids: set[int],
    fixture_audit_ids: set[int],
) -> Classification | None:
    evidence: list[str] = []
    proposed = job.data_provenance or "live"
    action = "preserve"

    if _job_fixture_source(job):
        evidence.append(f"fixture source/external_id: source={job.source!r}, external_id={job.external_id!r}")
        proposed = PROVENANCE_FIXTURE
        action = "delete_candidate"
    elif job.id in fixture_audit_ids:
        evidence.append("linked to workflow.ingest_fixture audit event")
        proposed = PROVENANCE_FIXTURE
        action = "delete_candidate"
    elif _job_e2e_external(job):
        evidence.append(f"E2E external_id prefix: {job.external_id!r}")
        proposed = PROVENANCE_TEST
        action = "delete_candidate"
    elif job.id in e2e_actor_ids:
        evidence.append(f"audit actor {E2E_ACTOR_EMAIL} on job resource")
        proposed = PROVENANCE_TEST
        action = "delete_candidate"
    elif _job_e2e_url(job) or _job_e2e_requisition(job):
        evidence.append(f"E2E URL or requisition: url={job.url!r}, req={job.requisition_id!r}")
        proposed = PROVENANCE_TEST
        action = "delete_candidate"
    elif _job_e2e_name_with_corroboration(job):
        evidence.append(f"E2E company name with corroboration: company={job.company!r}")
        proposed = PROVENANCE_TEST
        action = "delete_candidate"
    elif (job.source or "").lower().startswith("gmail"):
        raw = job.raw_payload or {}
        confidence = raw.get("parse_confidence") or raw.get("confidence")
        if confidence is not None and float(confidence) < GMAIL_LOW_CONFIDENCE:
            evidence.append(f"Gmail low parse confidence: {confidence}")
            proposed = PROVENANCE_GMAIL
            action = "delete_candidate"
        elif raw.get("quarantined") or raw.get("ignored_reason"):
            evidence.append(f"Gmail quarantine metadata: {raw.get('ignored_reason')}")
            proposed = PROVENANCE_GMAIL
            action = "delete_candidate"

    if proposed in {PROVENANCE_FIXTURE, PROVENANCE_TEST} and job.data_provenance not in {
        PROVENANCE_FIXTURE,
        PROVENANCE_TEST,
    }:
        action = "tag_" + proposed
    elif proposed in {PROVENANCE_FIXTURE, PROVENANCE_TEST} and job.data_provenance in {
        PROVENANCE_FIXTURE,
        PROVENANCE_TEST,
    }:
        action = "delete_candidate"
    elif proposed == job.data_provenance and proposed in {PROVENANCE_FIXTURE, PROVENANCE_TEST}:
        action = "delete_candidate"
    elif not evidence:
        return None

    return Classification(
        table="jobs",
        record_id=job.id,
        display_name=f"{job.company} — {job.title}",
        current_provenance=job.data_provenance or "live",
        proposed_provenance=proposed,
        proposed_action=action,
        evidence=evidence,
    )


def classify_company(db: Session, company: Company) -> Classification | None:
    jobs = db.query(Job).filter(Job.company_id == company.id).all()
    if not jobs:
        inferred = infer_provenance("")
        if company.data_provenance in {PROVENANCE_FIXTURE, PROVENANCE_TEST}:
            return Classification(
                table="companies",
                record_id=company.id,
                display_name=company.canonical_name,
                current_provenance=company.data_provenance,
                proposed_provenance=company.data_provenance,
                proposed_action="delete_candidate",
                evidence=["orphan company already tagged fixture/test"],
            )
        return None

    provs = {j.data_provenance for j in jobs}
    if provs <= {PROVENANCE_FIXTURE, PROVENANCE_TEST}:
        dominant = PROVENANCE_TEST if PROVENANCE_TEST in provs else PROVENANCE_FIXTURE
        evidence = [f"all {len(jobs)} linked job(s) are fixture/test"]
        action = "delete_candidate" if company.data_provenance in {PROVENANCE_FIXTURE, PROVENANCE_TEST} else f"tag_{dominant}"
        return Classification(
            table="companies",
            record_id=company.id,
            display_name=company.canonical_name,
            current_provenance=company.data_provenance or "live",
            proposed_provenance=dominant,
            proposed_action=action,
            evidence=evidence,
            linked_children=[f"job:{j.id}" for j in jobs],
        )
    return None


def classify_application(app: Application, job: Job | None) -> Classification | None:
    if job and job.data_provenance in {PROVENANCE_FIXTURE, PROVENANCE_TEST}:
        paths = [p for p in (app.resume_docx_path, app.resume_pdf_path) if p]
        return Classification(
            table="applications",
            record_id=app.id,
            display_name=f"Application for job {app.job_id}",
            current_provenance=app.data_provenance or "live",
            proposed_provenance=job.data_provenance,
            proposed_action="delete_candidate"
            if app.data_provenance in {PROVENANCE_FIXTURE, PROVENANCE_TEST}
            else f"tag_{job.data_provenance}",
            evidence=[f"linked job {job.id} provenance={job.data_provenance}"],
            artifact_paths=paths,
        )
    if app.data_provenance in {PROVENANCE_FIXTURE, PROVENANCE_TEST}:
        return Classification(
            table="applications",
            record_id=app.id,
            display_name=f"Application for job {app.job_id}",
            current_provenance=app.data_provenance,
            proposed_provenance=app.data_provenance,
            proposed_action="delete_candidate",
            evidence=["application already tagged fixture/test"],
        )
    return None


def _count_by_provenance(db: Session, model, column="data_provenance") -> dict[str, int]:
    col = getattr(model, column)
    rows = db.query(col, func.count()).group_by(col).all()
    return {str(k or "null"): int(v) for k, v in rows}


def build_inventory(db: Session) -> dict[str, Any]:
    e2e_actor_ids = _e2e_actor_job_ids(db)
    fixture_audit_ids = _fixture_audit_job_ids(db)

    classifications: list[Classification] = []

    for job in db.query(Job).order_by(Job.id).all():
        row = classify_job(job, e2e_actor_ids=e2e_actor_ids, fixture_audit_ids=fixture_audit_ids)
        if row:
            app = db.query(Application).filter(Application.job_id == job.id).one_or_none()
            if app:
                row.linked_children.append(f"application:{app.id}")
                versions = (
                    db.query(ApplicationDocumentVersion)
                    .filter(ApplicationDocumentVersion.application_id == app.id)
                    .all()
                )
                for v in versions:
                    row.linked_children.append(f"document_version:{v.id}")
                    if v.docx_path:
                        row.artifact_paths.append(v.docx_path)
                    if v.pdf_path:
                        row.artifact_paths.append(v.pdf_path)
            classifications.append(row)

    for company in db.query(Company).order_by(Company.id).all():
        row = classify_company(db, company)
        if row:
            classifications.append(row)

    for app in db.query(Application).order_by(Application.id).all():
        if any(c.table == "applications" and c.record_id == app.id for c in classifications):
            continue
        job = db.query(Job).filter(Job.id == app.job_id).one_or_none()
        row = classify_application(app, job)
        if row:
            classifications.append(row)

    # Gmail fixture messages
    for msg in db.query(ProcessedGmailMessage).filter(ProcessedGmailMessage.message_id.like("fixture-%")).all():
        classifications.append(
            Classification(
                table="processed_gmail_messages",
                record_id=msg.id,
                display_name=msg.message_id,
                current_provenance="fixture",
                proposed_provenance="fixture",
                proposed_action="delete_candidate",
                evidence=["gmail message_id fixture- prefix"],
            )
        )

    for review in db.query(GmailIngestReview).filter(GmailIngestReview.status == "quarantined").all():
        if review.job_id:
            classifications.append(
                Classification(
                    table="gmail_ingest_reviews",
                    record_id=review.id,
                    display_name=review.subject or f"review-{review.id}",
                    current_provenance="gmail",
                    proposed_provenance="gmail",
                    proposed_action="preserve",
                    evidence=[f"quarantined: {review.ignored_reason or 'low confidence'}"],
                    linked_children=[f"job:{review.job_id}"] if review.job_id else [],
                )
            )

    # E2E audit events (tag for optional cleanup, preserve by default)
    e2e_audits = db.query(AuditLog).filter(AuditLog.actor == E2E_ACTOR_EMAIL).count()

    before = {
        "jobs": _count_by_provenance(db, Job),
        "companies": _count_by_provenance(db, Company),
        "applications": _count_by_provenance(db, Application),
        "total_jobs": db.query(Job).count(),
        "total_companies": db.query(Company).count(),
        "total_applications": db.query(Application).count(),
        "e2e_audit_events": e2e_audits,
        "recruiter_signals": db.query(RecruiterSignal).count(),
        "gmail_reviews_quarantined": db.query(GmailIngestReview)
        .filter(GmailIngestReview.status == "quarantined")
        .count(),
    }

    delete_candidates = [c for c in classifications if c.proposed_action == "delete_candidate"]
    tag_candidates = [c for c in classifications if c.proposed_action.startswith("tag_")]

    after_delete = {
        "jobs_removed": sum(1 for c in delete_candidates if c.table == "jobs"),
        "companies_removed": sum(1 for c in delete_candidates if c.table == "companies"),
        "applications_removed": sum(1 for c in delete_candidates if c.table == "applications"),
    }

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "before_counts": before,
        "after_delete_estimates": after_delete,
        "tag_backfill_count": len(tag_candidates),
        "delete_candidate_count": len(delete_candidates),
        "classifications": classifications,
    }


def apply_provenance_backfill(db: Session, inventory: dict[str, Any]) -> int:
    """Apply tag_* actions only — never deletes."""
    updated = 0
    for item in inventory["classifications"]:
        if not item.proposed_action.startswith("tag_"):
            continue
        prov = item.proposed_provenance
        if item.table == "jobs":
            row = db.query(Job).filter(Job.id == item.record_id).one_or_none()
            if row and row.data_provenance != prov:
                row.data_provenance = prov
                updated += 1
        elif item.table == "companies":
            row = db.query(Company).filter(Company.id == item.record_id).one_or_none()
            if row and row.data_provenance != prov:
                row.data_provenance = prov
                updated += 1
        elif item.table == "applications":
            row = db.query(Application).filter(Application.id == item.record_id).one_or_none()
            if row and row.data_provenance != prov:
                row.data_provenance = prov
                updated += 1
    db.commit()
    return updated


def format_report(inventory: dict[str, Any]) -> str:
    lines = [
        "=== Aarohan Legacy Test/Fixture Inventory ===",
        f"Generated: {inventory['generated_at']}",
        "",
        "Before counts:",
    ]
    for key, val in inventory["before_counts"].items():
        if isinstance(val, dict):
            lines.append(f"  {key}: {val}")
        else:
            lines.append(f"  {key}: {val}")

    lines.extend(
        [
            "",
            f"Provenance backfill candidates (tag only): {inventory['tag_backfill_count']}",
            f"Delete candidates (after backfill + owner approval): {inventory['delete_candidate_count']}",
            "",
            "=== Detailed classifications ===",
            "table | id | display_name | current | proposed | action | evidence | children | artifacts",
            "------+----+--------------+---------+----------+--------+----------+----------+----------",
        ]
    )

    for c in inventory["classifications"]:
        ev = "; ".join(c.evidence)
        ch = ", ".join(c.linked_children) or "—"
        art = ", ".join(c.artifact_paths) or "—"
        lines.append(
            f"{c.table} | {c.record_id} | {c.display_name[:60]} | {c.current_provenance} | "
            f"{c.proposed_provenance} | {c.proposed_action} | {ev[:120]} | {ch[:80]} | {art[:80]}"
        )

    est = inventory["after_delete_estimates"]
    lines.extend(
        [
            "",
            "Estimated removals if owner approves delete phase:",
            f"  jobs: {est['jobs_removed']}",
            f"  companies: {est['companies_removed']}",
            f"  applications: {est['applications_removed']}",
            "",
            "DRY-RUN — no records deleted. Owner must approve before -Execute phase.",
        ]
    )
    return "\n".join(lines)
