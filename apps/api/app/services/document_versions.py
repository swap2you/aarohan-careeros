"""Immutable application document version management."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Application, ApplicationDocumentVersion, Job


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def allocate_version_number(db: Session, application: Application) -> int:
    locked = (
        db.query(Application)
        .filter(Application.id == application.id)
        .with_for_update()
        .one()
    )
    next_number = locked.latest_version_number + 1
    locked.latest_version_number = next_number
    application.latest_version_number = next_number
    db.add(locked)
    db.flush()
    return next_number


def version_output_dir(base_dir: Path, job_id: int, version_number: int) -> Path:
    path = base_dir / f"job_{job_id}" / f"v{version_number:02d}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_document_version(
    db: Session,
    *,
    application: Application,
    job: Job,
    docx_path: Path,
    pdf_path: Path,
    actor: str,
    template_version: str | None,
    prompt_version: str | None,
    model_version: str | None,
    factual_core_hash: str | None,
    metadata: dict | None = None,
) -> ApplicationDocumentVersion:
    if not application.id:
        db.flush()
        db.refresh(application)

    version_number = allocate_version_number(db, application)
    return _register_document_version(
        db,
        application=application,
        job=job,
        version_number=version_number,
        docx_path=docx_path,
        pdf_path=pdf_path,
        actor=actor,
        template_version=template_version,
        prompt_version=prompt_version,
        model_version=model_version,
        factual_core_hash=factual_core_hash,
        metadata=metadata,
    )


def register_document_version(
    db: Session,
    *,
    application: Application,
    job: Job,
    version_number: int,
    docx_path: Path,
    pdf_path: Path,
    actor: str,
    template_version: str | None,
    prompt_version: str | None,
    model_version: str | None,
    factual_core_hash: str | None,
    metadata: dict | None = None,
) -> ApplicationDocumentVersion:
    return _register_document_version(
        db,
        application=application,
        job=job,
        version_number=version_number,
        docx_path=docx_path,
        pdf_path=pdf_path,
        actor=actor,
        template_version=template_version,
        prompt_version=prompt_version,
        model_version=model_version,
        factual_core_hash=factual_core_hash,
        metadata=metadata,
    )


def _register_document_version(
    db: Session,
    *,
    application: Application,
    job: Job,
    version_number: int,
    docx_path: Path,
    pdf_path: Path,
    actor: str,
    template_version: str | None,
    prompt_version: str | None,
    model_version: str | None,
    factual_core_hash: str | None,
    metadata: dict | None,
) -> ApplicationDocumentVersion:
    submitted_exists = (
        db.query(ApplicationDocumentVersion)
        .filter(
            ApplicationDocumentVersion.application_id == application.id,
            ApplicationDocumentVersion.is_submitted_immutable.is_(True),
        )
        .count()
        > 0
    )
    if submitted_exists:
        immutable = (
            db.query(ApplicationDocumentVersion)
            .filter(
                ApplicationDocumentVersion.application_id == application.id,
                ApplicationDocumentVersion.is_submitted_immutable.is_(True),
            )
            .order_by(ApplicationDocumentVersion.version_number)
            .all()
        )
        for prior in immutable:
            if Path(prior.docx_path).exists() and Path(prior.docx_path).samefile(docx_path):
                raise ValueError("Cannot overwrite an immutable submitted document version.")
            if Path(prior.pdf_path).exists() and Path(prior.pdf_path).samefile(pdf_path):
                raise ValueError("Cannot overwrite an immutable submitted document version.")

    row = ApplicationDocumentVersion(
        application_id=application.id,
        version_number=version_number,
        docx_path=str(docx_path),
        pdf_path=str(pdf_path),
        checksum_sha256=file_checksum(docx_path),
        job_snapshot={
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "url": job.url,
            "source": job.source,
            "external_id": job.external_id,
            "requisition_id": job.requisition_id,
            "ats_job_id": job.ats_job_id,
        },
        template_version=template_version,
        prompt_version=prompt_version,
        model_version=model_version,
        factual_core_hash=factual_core_hash,
        approval_details=metadata,
        is_submitted_immutable=False,
        created_by=actor,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def mark_version_submitted(db: Session, application: Application, *, actor: str) -> ApplicationDocumentVersion:
    version = (
        db.query(ApplicationDocumentVersion)
        .filter(
            ApplicationDocumentVersion.application_id == application.id,
            ApplicationDocumentVersion.version_number == application.latest_version_number,
        )
        .one_or_none()
    )
    if not version:
        raise ValueError("No document version exists to mark as submitted.")
    if version.is_submitted_immutable:
        return version
    version.is_submitted_immutable = True
    application.submitted_version_id = version.id
    db.add(version)
    db.add(application)
    db.flush()
    return version


def list_versions(db: Session, application_id: int) -> list[ApplicationDocumentVersion]:
    return (
        db.query(ApplicationDocumentVersion)
        .filter(ApplicationDocumentVersion.application_id == application_id)
        .order_by(ApplicationDocumentVersion.version_number)
        .all()
    )


def copy_to_versioned_paths(
    *,
    output_dir: Path,
    job: Job,
    resume_profile: str,
    version_number: int,
) -> tuple[Path, Path]:
    date_stamp = datetime.utcnow().strftime("%Y%m%d")
    safe_company = "".join(ch if ch.isalnum() else "_" for ch in job.company)[:40]
    safe_role = "".join(ch if ch.isalnum() else "_" for ch in job.title)[:40]
    docx_path = output_dir / f"{safe_company}_{safe_role}_{resume_profile}_v{version_number:02d}_{date_stamp}.docx"
    pdf_path = output_dir / f"{safe_company}_{safe_role}_{resume_profile}_v{version_number:02d}_{date_stamp}.pdf"
    return docx_path, pdf_path
