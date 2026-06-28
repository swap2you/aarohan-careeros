from datetime import datetime
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Application, EvidenceItem, Job, WorkflowState
from app.services.ai_budget import enforce_budget, record_usage
from app.services.audit import write_audit
from app.services.career_vault import public_evidence_statements
from app.services.resume_builder import build_ats_docx, extract_keywords, load_resume_profile, map_keywords_to_evidence


def _output_dir() -> Path:
    path = Path(settings.generated_root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_contact() -> dict:
    root = Path(settings.career_vault_root)
    if not root.exists():
        root = Path(__file__).resolve().parents[4] / "career_vault"
    contact_path = root / "contact.yml"
    data = yaml.safe_load(contact_path.read_text(encoding="utf-8")) if contact_path.exists() else {}
    return data or {}


def _missing_evidence_warnings(db: Session) -> list[str]:
    rows = db.query(EvidenceItem).filter(EvidenceItem.public_use.is_(False)).all()
    warnings = []
    for row in rows:
        if row.status in {"TODO_VERIFY", "NEEDS_EVIDENCE"}:
            warnings.append(f"{row.evidence_id}: {row.statement[:120]}...")
    return warnings


def generate_application_packet(
    db: Session,
    job: Job,
    *,
    actor: str,
    resume_profile: str = "qe_leadership",
) -> Application:
    enforce_budget(db, estimated_cost=0.5, operation="packet_generation")
    job.state = WorkflowState.PACKET_GENERATING.value
    db.add(job)
    db.commit()

    evidence = public_evidence_statements(db)
    if not evidence:
        raise ValueError("No public-use evidence available for resume generation.")

    profile = load_resume_profile(resume_profile)
    contact = _load_contact()
    keywords = extract_keywords(job.description_text)
    keyword_mapping = map_keywords_to_evidence(keywords, evidence)
    missing_warnings = _missing_evidence_warnings(db)

    date_stamp = datetime.utcnow().strftime("%Y%m%d")
    safe_company = "".join(ch if ch.isalnum() else "_" for ch in job.company)[:40]
    safe_role = "".join(ch if ch.isalnum() else "_" for ch in job.title)[:40]
    output_dir = _output_dir() / f"job_{job.id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    docx_path = output_dir / f"{safe_company}_{safe_role}_{resume_profile}_{date_stamp}.docx"
    pdf_path = output_dir / f"{safe_company}_{safe_role}_{resume_profile}_{date_stamp}.pdf"

    formatting_checks = build_ats_docx(
        output_path=docx_path,
        contact=contact,
        profile=profile,
        evidence=evidence,
        job_title=job.title,
        company=job.company,
        keyword_mapping=keyword_mapping,
        missing_warnings=missing_warnings,
    )

    cover_letter = (
        f"Dear Hiring Team at {job.company},\n\n"
        f"I am interested in the {job.title} role. {profile.get('summary', '').strip()} "
        "I would welcome a conversation about how I can help your team deliver reliable, scalable quality outcomes.\n\n"
        f"Regards,\n{contact.get('name', 'Swapnil Patil')}"
    )
    recruiter_note = (
        f"Evidence-grounded packet for {job.company}. Profile={resume_profile}. "
        f"Keywords mapped: {len(keyword_mapping)}. Review internal notes before external submission."
    )
    fit_analysis = (
        f"Profile '{profile.get('name')}' selected for {job.title}. "
        f"Matched {len(keyword_mapping)} JD keywords to verified evidence."
    )
    change_report = {
        "profile": resume_profile,
        "evidence_count": len(evidence),
        "keywords_mapped": list(keyword_mapping.keys())[:20],
        "formatting_checks": formatting_checks,
    }

    try:
        from weasyprint import HTML

        html_parts = [
            "<html><head><style>body{font-family:Calibri,Arial,sans-serif;font-size:11pt;margin:40px;}</style></head><body>",
            f"<h1>{contact.get('name', 'Candidate')}</h1>",
            f"<p>{contact.get('email', '')} | {contact.get('linkedin', '')}</p>",
            f"<h2>Professional Summary</h2><p>{profile.get('summary', '')}</p>",
            "<h2>Professional Experience</h2><ul>",
            *[f"<li>{line}</li>" for line in evidence],
            "</ul>",
            f"<h2>Role Target</h2><p>{job.title} at {job.company}</p>",
            "</body></html>",
        ]
        HTML(string="".join(html_parts)).write_pdf(pdf_path)
    except Exception:
        pdf_path.write_text("\n".join(evidence), encoding="utf-8")

    application = job.application or Application(job_id=job.id)
    application.cover_letter = cover_letter
    application.recruiter_note = recruiter_note
    application.fit_analysis = fit_analysis
    application.resume_profile = resume_profile
    application.resume_docx_path = str(docx_path)
    application.resume_pdf_path = str(pdf_path)
    application.packet_metadata = {
        "change_report": change_report,
        "missing_evidence_warnings": missing_warnings,
        "keyword_mapping": keyword_mapping,
        "preview_text": fit_analysis + "\n\n" + cover_letter[:1000],
    }
    application.state = WorkflowState.PACKET_READY.value
    application.updated_at = datetime.utcnow()
    job.state = WorkflowState.PACKET_READY.value

    db.add(application)
    db.add(job)
    db.commit()
    db.refresh(application)

    try:
        from app.services.integrations import get_drive_client

        drive = get_drive_client(db)
        docx_uri = drive.upload_file(str(docx_path), docx_path.name)
        pdf_uri = drive.upload_file(str(pdf_path), pdf_path.name)
        metadata = application.packet_metadata or {}
        metadata["drive_links"] = {"docx": docx_uri, "pdf": pdf_uri}
        application.packet_metadata = metadata
        db.add(application)
        db.commit()
        db.refresh(application)
    except Exception:
        pass

    record_usage(db, operation="packet_generation", cost_usd=0.5, job_id=job.id)
    write_audit(
        db,
        event_type="packet.generated",
        actor=actor,
        resource_type="application",
        resource_id=str(application.id),
        details={"job_id": job.id, "profile": resume_profile, "evidence_count": len(evidence)},
    )
    return application
