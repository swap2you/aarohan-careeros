"""Duplicate application risk and company registry."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy.orm import Session

from app.models import Application, ApplicationLedger, DuplicateOverride, Job, WorkflowState

POLICY_VERSION = "r2.1.0"
DEFAULT_CAUTION_DAYS = 180
DEFAULT_SPACING_DAYS = 14
MAX_ACTIVE_PER_COMPANY = 2

ACTIVE_STATUSES = {
    WorkflowState.SHORTLISTED.value,
    WorkflowState.PACKET_GENERATING.value,
    WorkflowState.PACKET_READY.value,
    WorkflowState.NEEDS_EDIT.value,
    WorkflowState.APPROVED_FOR_SUBMISSION.value,
    WorkflowState.SUBMITTED.value,
    WorkflowState.FOLLOW_UP_DUE.value,
    WorkflowState.INTERVIEW_SIGNAL.value,
    WorkflowState.INTERVIEW_SCHEDULED.value,
    WorkflowState.OFFER.value,
}


class RiskLevel(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


class ApplicationMode(str, Enum):
    MANUAL = "MANUAL"
    ASSISTED = "ASSISTED"
    AUTONOMOUS_LOCKED = "AUTONOMOUS_LOCKED"


AUTONOMOUS_REJECT_MESSAGE = (
    "Autonomous submission is disabled. Automatic applications can send duplicate, "
    "inaccurate, or low-quality submissions and may violate job-site rules. "
    "Use Assisted mode and review the final application before submitting."
)


def normalize_company_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_title(title: str) -> str:
    return normalize_company_name(title)


def description_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.lower().strip())[:8000]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


@dataclass
class DuplicateRiskResult:
    level: RiskLevel
    indicator: str
    summary: str
    reasons: list[str] = field(default_factory=list)
    matched_ledger_ids: list[int] = field(default_factory=list)
    policy_version: str = POLICY_VERSION
    can_override: bool = False

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "indicator": self.indicator,
            "summary": self.summary,
            "reasons": self.reasons,
            "matched_ledger_ids": self.matched_ledger_ids,
            "policy_version": self.policy_version,
            "can_override": self.can_override,
        }


def resolve_or_create_company(db: Session, company_name: str):
    from app.models import Company, CompanyAlias

    normalized = normalize_company_name(company_name)
    alias = db.query(CompanyAlias).filter(CompanyAlias.normalized_alias == normalized).first()
    if alias:
        return alias.company
    company = db.query(Company).filter(Company.normalized_name == normalized).one_or_none()
    if company:
        return company
    company = Company(
        canonical_name=company_name.strip(),
        normalized_name=normalized,
        created_at=datetime.utcnow(),
    )
    db.add(company)
    db.flush()
    db.add(
        CompanyAlias(
            company_id=company.id,
            alias=company_name.strip(),
            normalized_alias=normalized,
        )
    )
    db.flush()
    return company


def link_job_to_company(db: Session, job: Job) -> None:
    company = resolve_or_create_company(db, job.company)
    job.company_id = company.id
    if not job.description_fingerprint and job.description_text:
        job.description_fingerprint = description_fingerprint(job.description_text)
    job.normalized_title = normalize_title(job.title)
    db.add(job)


def evaluate_duplicate_risk(
    db: Session,
    job: Job,
    *,
    caution_days: int = DEFAULT_CAUTION_DAYS,
    spacing_days: int = DEFAULT_SPACING_DAYS,
    max_active: int = MAX_ACTIVE_PER_COMPANY,
) -> DuplicateRiskResult:
    if not job.company_id:
        link_job_to_company(db, job)
        db.commit()
        db.refresh(job)

    override = (
        db.query(DuplicateOverride)
        .filter(DuplicateOverride.job_id == job.id)
        .order_by(DuplicateOverride.created_at.desc())
        .first()
    )
    if override:
        return DuplicateRiskResult(
            level=RiskLevel.GREEN,
            indicator="Override recorded",
            summary=f"Duplicate check overridden: {override.reason[:120]}",
            reasons=["User override with audit trail"],
            matched_ledger_ids=override.matched_records or [],
            can_override=False,
        )

    ledger_rows = (
        db.query(ApplicationLedger)
        .filter(
            ApplicationLedger.company_id == job.company_id,
            ApplicationLedger.job_id != job.id,
        )
        .order_by(ApplicationLedger.updated_at.desc())
        .all()
    )

    now = datetime.utcnow()
    reasons: list[str] = []
    matched: list[int] = []

    for row in ledger_rows:
        matched.append(row.id)
        if job.requisition_id and row.requisition_id == job.requisition_id:
            return DuplicateRiskResult(
                level=RiskLevel.RED,
                indicator="Exact duplicate — blocked",
                summary="Same employer requisition ID was already submitted.",
                reasons=[f"Requisition {job.requisition_id} submitted {row.submitted_at or row.created_at}"],
                matched_ledger_ids=matched,
                can_override=True,
            )
        if job.ats_job_id and row.ats_job_id == job.ats_job_id:
            return DuplicateRiskResult(
                level=RiskLevel.RED,
                indicator="Exact duplicate — blocked",
                summary="Same ATS job ID was already submitted.",
                reasons=[f"ATS job {job.ats_job_id}"],
                matched_ledger_ids=matched,
                can_override=True,
            )
        if job.url and row.application_url and row.application_url.rstrip("/") == job.url.rstrip("/"):
            return DuplicateRiskResult(
                level=RiskLevel.RED,
                indicator="Exact duplicate — blocked",
                summary="Same application URL was already used.",
                reasons=[row.application_url],
                matched_ledger_ids=matched,
                can_override=True,
            )

    active_count = sum(1 for r in ledger_rows if r.status in ACTIVE_STATUSES)
    if active_count >= max_active:
        reasons.append(f"{active_count} active applications at this company (max {max_active})")

    recent = [
        r
        for r in ledger_rows
        if r.submitted_at and (now - r.submitted_at).days <= spacing_days
    ]
    if recent:
        reasons.append(f"Application within last {spacing_days} days")

    caution = [
        r
        for r in ledger_rows
        if r.submitted_at and (now - r.submitted_at).days <= caution_days
    ]
    if caution and not reasons:
        reasons.append(f"Prior application within {caution_days}-day caution window")

    if job.description_fingerprint:
        for row in ledger_rows:
            if (
                row.description_fingerprint == job.description_fingerprint
                and row.normalized_title == normalize_title(job.title)
            ):
                return DuplicateRiskResult(
                    level=RiskLevel.RED,
                    indicator="Exact duplicate — blocked",
                    summary="Same company, role, and description fingerprint already submitted.",
                    reasons=["Description fingerprint match"],
                    matched_ledger_ids=matched,
                    can_override=True,
                )

    if reasons:
        return DuplicateRiskResult(
            level=RiskLevel.AMBER,
            indicator="Prior company application",
            summary="Review prior applications before proceeding.",
            reasons=reasons,
            matched_ledger_ids=matched[:5],
            can_override=True,
        )

    return DuplicateRiskResult(
        level=RiskLevel.GREEN,
        indicator="No known conflict",
        summary="No duplicate-application conflicts detected.",
        reasons=[],
        matched_ledger_ids=[],
        can_override=False,
    )


def record_ledger_from_application(
    db: Session,
    application: Application,
    *,
    actor: str,
    status: str | None = None,
) -> ApplicationLedger:
    from app.models import ApplicationEvent

    job = application.job
    if not job:
        raise ValueError("Application has no job")
    link_job_to_company(db, job)
    row = (
        db.query(ApplicationLedger)
        .filter(
            ApplicationLedger.company_id == job.company_id,
            ApplicationLedger.application_id == application.id,
        )
        .one_or_none()
    )
    if not row:
        row = ApplicationLedger(
            company_id=job.company_id,
            job_id=job.id,
            application_id=application.id,
            requisition_id=job.requisition_id,
            ats_job_id=job.ats_job_id,
            application_url=job.url,
            normalized_title=normalize_title(job.title),
            description_fingerprint=job.description_fingerprint,
            status=status or application.state,
            submitted_at=application.submitted_at,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
    else:
        row.status = status or application.state
        row.updated_at = datetime.utcnow()
        if application.submitted_at:
            row.submitted_at = application.submitted_at
    db.flush()
    db.add(
        ApplicationEvent(
            ledger_id=row.id,
            event_type="status_update",
            actor_email=actor,
            notes=f"Status {row.status}",
            event_metadata={"application_id": application.id},
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    db.refresh(row)
    return row


def reject_autonomous_submission(mode: str) -> None:
    if mode.upper() == ApplicationMode.AUTONOMOUS_LOCKED.value or mode.upper() == "AUTONOMOUS":
        raise ValueError(AUTONOMOUS_REJECT_MESSAGE)
