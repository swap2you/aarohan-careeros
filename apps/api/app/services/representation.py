"""Vendor/client representation conflict detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session

from app.models import Job, RepresentationOverride, RepresentationRecord
from app.services.duplicate_risk import RiskLevel, normalize_company_name, normalize_title


POLICY_VERSION = "r2.5.0"


class RepresentationStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DECLINED = "declined"


@dataclass
class RepresentationRiskResult:
    level: RiskLevel
    indicator: str
    summary: str
    reasons: list[str] = field(default_factory=list)
    matched_record_ids: list[int] = field(default_factory=list)
    policy_version: str = POLICY_VERSION
    can_override: bool = False

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "indicator": self.indicator,
            "summary": self.summary,
            "reasons": self.reasons,
            "matched_record_ids": self.matched_record_ids,
            "policy_version": self.policy_version,
            "can_override": self.can_override,
        }


def _is_active(record: RepresentationRecord, now: datetime) -> bool:
    if record.status != RepresentationStatus.ACTIVE.value:
        return False
    if record.representation_end and record.representation_end < now:
        return False
    return True


def evaluate_representation_risk(db: Session, job: Job) -> RepresentationRiskResult:
    override = (
        db.query(RepresentationOverride)
        .filter(RepresentationOverride.job_id == job.id)
        .order_by(RepresentationOverride.created_at.desc())
        .first()
    )
    if override:
        return RepresentationRiskResult(
            level=RiskLevel.GREEN,
            indicator="Representation override recorded",
            summary=f"Vendor conflict overridden: {override.reason[:120]}",
            reasons=["User override with audit trail"],
            can_override=False,
        )

    normalized_client = normalize_company_name(job.company)
    now = datetime.utcnow()
    records = (
        db.query(RepresentationRecord)
        .filter(RepresentationRecord.normalized_client == normalized_client)
        .order_by(RepresentationRecord.updated_at.desc())
        .all()
    )

    active = [r for r in records if _is_active(r, now)]
    expired = [r for r in records if r.status == RepresentationStatus.EXPIRED.value or (
        r.representation_end and r.representation_end < now
    )]

    if job.requisition_id:
        for record in active:
            if record.requisition_id and record.requisition_id == job.requisition_id:
                return RepresentationRiskResult(
                    level=RiskLevel.RED,
                    indicator="Vendor representation conflict",
                    summary=(
                        f"Active representation by {record.vendor_name} exists for this client "
                        f"and requisition {job.requisition_id}."
                    ),
                    reasons=[
                        f"Vendor {record.vendor_name} submitted for requisition {record.requisition_id}",
                        "Another vendor submission may conflict with representation terms.",
                    ],
                    matched_record_ids=[record.id],
                    can_override=True,
                )

    if active:
        job_title = normalize_title(job.title)
        for record in active:
            if record.role_title and normalize_title(record.role_title) == job_title:
                return RepresentationRiskResult(
                    level=RiskLevel.RED,
                    indicator="Vendor representation conflict",
                    summary=f"Active {record.vendor_name} representation for a similar role at {job.company}.",
                    reasons=[f"Active representation role: {record.role_title}"],
                    matched_record_ids=[record.id],
                    can_override=True,
                )
        return RepresentationRiskResult(
            level=RiskLevel.AMBER,
            indicator="Active vendor representation",
            summary=f"Active representation exists for {job.company}. Confirm direct application is allowed.",
            reasons=[f"{record.vendor_name} representation active" for record in active[:3]],
            matched_record_ids=[r.id for r in active[:3]],
            can_override=True,
        )

    if expired:
        return RepresentationRiskResult(
            level=RiskLevel.AMBER,
            indicator="Expired representation on file",
            summary="Prior vendor representation expired but remains visible for review.",
            reasons=[f"{record.vendor_name} representation ended {record.representation_end or 'unknown'}" for record in expired[:2]],
            matched_record_ids=[r.id for r in expired[:2]],
            can_override=False,
        )

    return RepresentationRiskResult(
        level=RiskLevel.GREEN,
        indicator="No representation conflict",
        summary="No active vendor representation conflicts detected.",
        reasons=[],
        matched_record_ids=[],
        can_override=False,
    )
