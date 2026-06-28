from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Application, User
from app.services.career_vault import public_evidence_statements, sync_evidence_registry
from app.services.document_quality import (
    baseline_resume_hash,
    run_document_quality_report,
    template_config,
)
from app.services.factual_core import validate_factual_core

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/templates")
def list_templates(_: User = Depends(get_current_user)) -> dict:
    return template_config()


@router.get("/baseline-resume")
def baseline_resume(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    sync_evidence_registry(db)
    evidence = public_evidence_statements(db)
    return {
        "evidence_count": len(evidence),
        "baseline_hash": baseline_resume_hash(db),
        "statements_preview": evidence[:10],
        "generation_mode": template_config().get("generation_mode"),
    }


@router.get("/applications/{application_id}/quality")
def application_quality(
    application_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    application = db.query(Application).filter(Application.id == application_id).one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    meta = application.packet_metadata or {}
    if meta.get("document_quality"):
        return meta["document_quality"]
    if not application.resume_docx_path:
        raise HTTPException(status_code=404, detail="No generated documents for this application")
    job = application.job
    if not job:
        raise HTTPException(status_code=404, detail="Application has no job")
    report = run_document_quality_report(
        db,
        docx_path=Path(application.resume_docx_path),
        pdf_path=Path(application.resume_pdf_path or application.resume_docx_path),
        resume_text=meta.get("preview_text", ""),
        job_title=job.title,
        company=job.company,
        profile_name=application.resume_profile or "qe_leadership",
        keyword_mapping=meta.get("keyword_mapping", {}),
    )
    return report


@router.post("/applications/{application_id}/validate")
def validate_application_documents(
    application_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    application = db.query(Application).filter(Application.id == application_id).one_or_none()
    if not application or not application.resume_docx_path:
        raise HTTPException(status_code=404, detail="Application or documents not found")
    job = application.job
    meta = application.packet_metadata or {}
    report = run_document_quality_report(
        db,
        docx_path=Path(application.resume_docx_path),
        pdf_path=Path(application.resume_pdf_path or application.resume_docx_path),
        resume_text=meta.get("preview_text", ""),
        job_title=job.title if job else "",
        company=job.company if job else "",
        profile_name=application.resume_profile or "qe_leadership",
        keyword_mapping=meta.get("keyword_mapping", {}),
    )
    factual = validate_factual_core(db, resume_text=meta.get("preview_text", ""))
    report["factual_core"] = factual.to_dict()
    report["passed"] = report["passed"] and factual.consistent
    return report
