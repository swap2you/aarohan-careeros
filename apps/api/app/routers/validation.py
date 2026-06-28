from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Application, User, ValidationRun
from app.services.audit import write_audit
from app.services.validation_runner import run_local_validation

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/run")
def run_validation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    run = run_local_validation(db, actor=current_user.email)
    write_audit(db, event_type="validation.run", actor=current_user.email, resource_id=str(run.id))
    return {"id": run.id, "status": run.status, "summary": run.summary, "results": run.results}


@router.get("/latest")
def latest_validation(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    run = db.query(ValidationRun).order_by(ValidationRun.created_at.desc()).first()
    if not run:
        return {"status": "NONE"}
    return {"id": run.id, "status": run.status, "summary": run.summary, "results": run.results, "created_at": run.created_at}


@router.get("/applications/{application_id}/preview")
def preview_packet(
    application_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    app_row = db.query(Application).filter(Application.id == application_id).one_or_none()
    if not app_row:
        return {"error": "not_found"}
    return {
        "application_id": app_row.id,
        "state": app_row.state,
        "cover_letter": app_row.cover_letter,
        "recruiter_note": app_row.recruiter_note,
        "fit_analysis": app_row.fit_analysis,
        "metadata": app_row.packet_metadata,
        "resume_docx_path": app_row.resume_docx_path,
        "resume_pdf_path": app_row.resume_pdf_path,
    }


@router.get("/applications/{application_id}/download/{file_type}")
def download_packet(
    application_id: int,
    file_type: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    app_row = db.query(Application).filter(Application.id == application_id).one_or_none()
    if not app_row:
        return {"error": "not_found"}
    path = app_row.resume_docx_path if file_type == "docx" else app_row.resume_pdf_path
    if not path:
        return {"error": "file_missing"}
    media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if file_type == "pdf":
        media = "application/pdf"
    return FileResponse(path, media_type=media, filename=Path(path).name)
