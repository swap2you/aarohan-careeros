"""Assisted application workflow — prepare mappings, enforce stop-before-submit."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import Application, Job, WorkflowState
from app.services.ats_detection import AtsDetectionResult, AtsProvider, detect_ats
from app.services.audit import write_audit
from app.services.document_versions import list_versions
from app.services.duplicate_risk import RiskLevel, evaluate_duplicate_risk, reject_autonomous_submission
from app.services.representation import evaluate_representation_risk
from app.services.workflow_timeline import record_timeline_event

ASSISTED_STOP_MESSAGE = (
    "Aarohan has not submitted this application. "
    "Review every field on the employer site and press Submit yourself."
)

SUBMIT_FORBIDDEN_MESSAGE = (
    "Aarohan cannot perform final external submission. "
    "Use the employer Submit button after reviewing all fields."
)

USER_REQUIRED_TOPICS = (
    "work_authorization",
    "sponsorship",
    "salary_expectations",
    "voluntary_demographics",
    "legal_attestations",
    "relocation",
    "travel",
    "conflicts_of_interest",
)


class FieldStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    USER_REQUIRED = "USER_REQUIRED"
    MISSING = "MISSING"


@dataclass
class AssistedField:
    key: str
    label: str
    value: str | None
    status: FieldStatus
    notes: str | None = None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "status": self.status.value,
            "notes": self.notes,
        }


@dataclass
class AssistedPrepareResult:
    application_id: int
    job_id: int
    mode: str
    ats: AtsDetectionResult
    official_url: str
    duplicate_risk: dict
    representation_risk: dict
    artifact_version_number: int | None
    submitted_version_number: int | None
    fields: list[AssistedField] = field(default_factory=list)
    unanswered_questions: list[str] = field(default_factory=list)
    user_required_topics: list[str] = field(default_factory=list)
    can_proceed: bool = False
    blocked_reason: str | None = None
    stop_before_submit_message: str = ASSISTED_STOP_MESSAGE

    def to_dict(self) -> dict:
        return {
            "application_id": self.application_id,
            "job_id": self.job_id,
            "mode": self.mode,
            "ats": self.ats.to_dict(),
            "official_url": self.official_url,
            "duplicate_risk": self.duplicate_risk,
            "representation_risk": self.representation_risk,
            "artifact_version_number": self.artifact_version_number,
            "submitted_version_number": self.submitted_version_number,
            "fields": [f.to_dict() for f in self.fields],
            "unanswered_questions": self.unanswered_questions,
            "user_required_topics": list(USER_REQUIRED_TOPICS),
            "can_proceed": self.can_proceed,
            "blocked_reason": self.blocked_reason,
            "stop_before_submit_message": self.stop_before_submit_message,
        }


def _load_contact() -> dict:
    from pathlib import Path

    import yaml

    from app.config import settings

    root = Path(settings.career_vault_root)
    contact_path = root / "contact.yml"
    if not contact_path.exists():
        return {}
    return yaml.safe_load(contact_path.read_text(encoding="utf-8")) or {}


def _approved_common_answers(contact: dict) -> dict[str, str]:
    answers = contact.get("application_answers") or {}
    return {str(k): str(v) for k, v in answers.items() if v}


def build_field_mapping(
    job: Job,
    application: Application,
    *,
    ats: AtsDetectionResult,
) -> list[AssistedField]:
    contact = _load_contact()
    common = _approved_common_answers(contact)
    fields: list[AssistedField] = [
        AssistedField("name", "Full name", contact.get("name"), FieldStatus.READY if contact.get("name") else FieldStatus.MISSING),
        AssistedField("email", "Email", contact.get("email"), FieldStatus.READY if contact.get("email") else FieldStatus.MISSING),
        AssistedField("phone", "Phone", contact.get("phone"), FieldStatus.READY if contact.get("phone") else FieldStatus.REVIEW, notes="Confirm format matches employer form"),
        AssistedField("location", "Location", contact.get("location") or job.location, FieldStatus.REVIEW, notes="Confirm city/state or remote preference"),
        AssistedField("linkedin", "LinkedIn", contact.get("linkedin"), FieldStatus.READY if contact.get("linkedin") else FieldStatus.MISSING),
        AssistedField("portfolio", "Portfolio / website", contact.get("portfolio"), FieldStatus.READY if contact.get("portfolio") else FieldStatus.MISSING),
        AssistedField(
            "resume",
            "Resume file",
            application.resume_pdf_path or application.resume_docx_path,
            FieldStatus.READY if application.resume_pdf_path or application.resume_docx_path else FieldStatus.MISSING,
        ),
        AssistedField(
            "cover_letter",
            "Cover letter",
            (application.cover_letter or "")[:500] or None,
            FieldStatus.READY if application.cover_letter else FieldStatus.MISSING,
        ),
    ]
    for key, value in common.items():
        fields.append(
            AssistedField(
                f"answer_{key}",
                key.replace("_", " ").title(),
                value,
                FieldStatus.READY,
                notes="Approved common answer from career vault",
            )
        )

    if ats.provider == AtsProvider.GREENHOUSE:
        fields.append(AssistedField("greenhouse_source", "How did you hear about us?", common.get("referral_source"), FieldStatus.REVIEW))
    elif ats.provider == AtsProvider.LEVER:
        fields.append(AssistedField("lever_links", "Links", contact.get("linkedin") or contact.get("portfolio"), FieldStatus.REVIEW))
    elif ats.provider == AtsProvider.ASHBY:
        fields.append(AssistedField("ashby_questionnaire", "Ashby questionnaire", None, FieldStatus.USER_REQUIRED, notes="Review each Ashby custom question manually"))

    return fields


def _domain_matches_official(job: Job, ats: AtsDetectionResult) -> bool:
    job_host = urlparse(job.url).netloc.lower()
    return job_host == ats.host or job_host.endswith(ats.host) or ats.host in job_host


def prepare_assisted_apply(db: Session, application: Application, *, actor: str) -> AssistedPrepareResult:
    reject_autonomous_submission("ASSISTED")
    job = application.job
    if not job:
        raise ValueError("Application has no linked job")

    ats = detect_ats(job.url)
    dup = evaluate_duplicate_risk(db, job)
    rep = evaluate_representation_risk(db, job)
    versions = list_versions(db, application.id)
    latest = versions[-1].version_number if versions else application.latest_version_number or None
    submitted = next((v.version_number for v in versions if v.is_submitted_immutable), None)

    result = AssistedPrepareResult(
        application_id=application.id,
        job_id=job.id,
        mode="ASSISTED",
        ats=ats,
        official_url=job.url,
        duplicate_risk=dup.to_dict(),
        representation_risk=rep.to_dict(),
        artifact_version_number=latest,
        submitted_version_number=submitted,
    )

    if ats.provider == AtsProvider.PROHIBITED:
        result.blocked_reason = "Assisted mode is not available for this job site."
        return result

    if not ats.assisted_available:
        result.blocked_reason = "Unsupported ATS — use Manual mode."
        return result

    if dup.level == RiskLevel.RED:
        result.blocked_reason = f"{dup.indicator}: {dup.summary}"
        return result

    if rep.level == RiskLevel.RED:
        result.blocked_reason = f"{rep.indicator}: {rep.summary}"
        return result

    if application.state not in {
        WorkflowState.PACKET_READY.value,
        WorkflowState.APPROVED_FOR_SUBMISSION.value,
    }:
        result.blocked_reason = "Approve the packet before assisted apply."
        return result

    if not _domain_matches_official(job, ats):
        result.blocked_reason = "Official application domain could not be verified."
        return result

    result.fields = build_field_mapping(job, application, ats=ats)
    result.unanswered_questions = [
        "Work authorization and sponsorship (if no approved vault answer)",
        "Salary expectations (if requested)",
        "Voluntary demographic questions",
        "Legal attestations and e-signature confirmations",
        "Custom employer questions without approved answers",
    ]
    missing = [f.label for f in result.fields if f.status == FieldStatus.MISSING]
    if missing:
        result.unanswered_questions.extend([f"Missing: {label}" for label in missing])

    result.can_proceed = True
    write_audit(
        db,
        event_type="assisted.prepare",
        actor=actor,
        resource_type="application",
        resource_id=str(application.id),
        details={"ats": ats.provider.value, "job_id": job.id},
    )
    db.commit()
    return result


def record_assisted_open(db: Session, application: Application, *, actor: str, notes: str | None = None) -> None:
    record_timeline_event(
        db,
        application_id=application.id,
        job_id=application.job_id,
        event_type="assisted_application_opened",
        title="Assisted application opened",
        description=notes or ASSISTED_STOP_MESSAGE,
        actor_email=actor,
        metadata={"mode": "ASSISTED"},
    )
    write_audit(
        db,
        event_type="assisted.open",
        actor=actor,
        resource_type="application",
        resource_id=str(application.id),
        details={"notes": notes, "opened_at": datetime.utcnow().isoformat()},
    )
    db.commit()


def reject_assisted_submit() -> None:
    raise ValueError(SUBMIT_FORBIDDEN_MESSAGE)
