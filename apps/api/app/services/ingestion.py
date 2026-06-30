from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Job, WorkflowState
from app.services.audit import write_audit
from app.services.duplicate_risk import description_fingerprint, link_job_to_company
from app.services.normalization import build_dedupe_key, parse_salary_range
from app.services.sanitize import html_to_text
from app.services.sanitize import sanitize_html
from app.services.provenance import infer_provenance
from app.services.scoring import score_job


def ingest_job(db: Session, payload: dict, *, actor: str = "system") -> Job:
    source = payload["source"]
    external_id = payload["external_id"]
    existing = (
        db.query(Job)
        .filter(Job.source == source, Job.external_id == external_id)
        .one_or_none()
    )
    if existing:
        return existing

    description_html = sanitize_html(payload.get("description_html", ""))
    description_text = payload.get("description_text") or html_to_text(description_html)
    salary_text = payload.get("salary_text") or description_text
    salary_min, salary_max = parse_salary_range(salary_text)
    if payload.get("salary_min") is not None:
        salary_min = payload["salary_min"]
    if payload.get("salary_max") is not None:
        salary_max = payload["salary_max"]

    company = payload["company"]
    title = payload["title"]
    location = payload.get("location")
    dedupe_key = build_dedupe_key(company, title, location)

    duplicate = db.query(Job).filter(Job.dedupe_key == dedupe_key).one_or_none()
    if duplicate:
        write_audit(
            db,
            event_type="job.deduplicated",
            actor=actor,
            resource_type="job",
            resource_id=str(duplicate.id),
            details={"incoming_external_id": external_id, "source": source},
        )
        return duplicate

    posted_at = payload.get("posted_at")
    if isinstance(posted_at, str):
        posted_at = datetime.fromisoformat(posted_at.replace("Z", "+00:00")).replace(tzinfo=None)

    discovered_at = datetime.utcnow()
    freshness_hours = None
    if posted_at:
        freshness_hours = (discovered_at - posted_at).total_seconds() / 3600

    provenance = infer_provenance(source, explicit=payload.get("data_provenance"), payload=payload)

    job = Job(
        source=source,
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        workplace_type=payload.get("workplace_type"),
        salary_min=salary_min,
        salary_max=salary_max,
        description_html=description_html,
        description_text=description_text or "",
        url=payload["url"],
        posted_at=posted_at,
        discovered_at=discovered_at,
        freshness_hours=freshness_hours,
        dedupe_key=dedupe_key,
        state=WorkflowState.NORMALIZED.value,
        raw_payload=payload,
        requisition_id=payload.get("requisition_id"),
        ats_job_id=payload.get("ats_job_id"),
        description_fingerprint=description_fingerprint(description_text or ""),
        data_provenance=provenance,
    )
    db.add(job)
    db.flush()
    link_job_to_company(db, job)
    db.commit()
    db.refresh(job)

    score_job(db, job)
    write_audit(
        db,
        event_type="job.ingested",
        actor=actor,
        resource_type="job",
        resource_id=str(job.id),
        details={"source": source, "company": company, "title": title},
    )
    return job
