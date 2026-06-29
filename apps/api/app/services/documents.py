from datetime import datetime
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Application, EvidenceItem, Job, WorkflowState
from app.services.ai_budget import enforce_budget, record_usage
from app.services.audit import write_audit
from app.services.career_vault import public_evidence_statements
from app.services.document_quality import run_document_quality_report, template_config
from app.services.document_versions import (
    allocate_version_number,
    register_document_version,
    version_output_dir,
)
from app.services.duplicate_risk import RiskLevel, evaluate_duplicate_risk, record_ledger_from_application
from app.services.factual_core import validate_factual_core
from app.services.representation import evaluate_representation_risk
from app.services.resume_builder import build_ats_docx, extract_keywords, load_resume_profile, map_keywords_to_evidence
from app.services.workflow_timeline import record_timeline_event


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
    skip_duplicate_block: bool = False,
) -> Application:
    enforce_budget(db, estimated_cost=0.5, operation="packet_generation")
    risk = evaluate_duplicate_risk(db, job)
    if risk.level == RiskLevel.RED and not skip_duplicate_block:
        raise ValueError(f"{risk.indicator}: {risk.summary}")

    rep_risk = evaluate_representation_risk(db, job)
    if rep_risk.level == RiskLevel.RED and not skip_duplicate_block:
        raise ValueError(f"{rep_risk.indicator}: {rep_risk.summary}")

    application = job.application or Application(job_id=job.id, latest_version_number=0, data_provenance=job.data_provenance)
    db.add(application)
    previous_job_state = job.state
    job.state = WorkflowState.PACKET_GENERATING.value
    db.add(job)
    db.flush()

    evidence = public_evidence_statements(db)
    if not evidence:
        raise ValueError("No public-use evidence available for resume generation.")

    profile = load_resume_profile(resume_profile)
    contact = _load_contact()
    keywords = extract_keywords(job.description_text or "")
    keyword_mapping = map_keywords_to_evidence(keywords, evidence)
    missing_warnings = _missing_evidence_warnings(db)

    version_number = allocate_version_number(db, application)
    output_dir = version_output_dir(_output_dir(), job.id, version_number)
    date_stamp = datetime.utcnow().strftime("%Y%m%d")
    safe_company = "".join(ch if ch.isalnum() else "_" for ch in job.company)[:40]
    safe_role = "".join(ch if ch.isalnum() else "_" for ch in job.title)[:40]
    docx_path = output_dir / f"{safe_company}_{safe_role}_{resume_profile}_v{version_number:02d}_{date_stamp}.docx"
    pdf_path = output_dir / f"{safe_company}_{safe_role}_{resume_profile}_v{version_number:02d}_{date_stamp}.pdf"

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
        "template_version": template_config().get("template_version"),
        "prompt_version": template_config().get("prompt_version"),
        "model_version": template_config().get("model_version"),
    }
    resume_preview = fit_analysis + "\n\n" + "\n".join(evidence)
    factual = validate_factual_core(db, resume_text=resume_preview)
    if not factual.consistent:
        raise ValueError(f"{factual.indicator}: {'; '.join(factual.contradictions)}")

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

    quality = run_document_quality_report(
        db,
        docx_path=docx_path,
        pdf_path=pdf_path,
        resume_text=resume_preview,
        job_title=job.title,
        company=job.company,
        profile_name=profile.get("name", resume_profile),
        keyword_mapping=keyword_mapping,
    )
    if not quality["passed"]:
        issues = quality["ats_diagnostics"].get("issues", [])[:3]
        comparison_msg = quality.get("docx_pdf_comparison", {}).get("message", "")
        detail = "; ".join(issues) or comparison_msg or "quality validation failed"
        raise ValueError(f"Document quality check failed: {detail}")

    cfg = template_config()
    doc_version = register_document_version(
        db,
        application=application,
        job=job,
        version_number=version_number,
        docx_path=docx_path,
        pdf_path=pdf_path,
        actor=actor,
        template_version=cfg.get("template_version"),
        prompt_version=cfg.get("prompt_version"),
        model_version=cfg.get("model_version"),
        factual_core_hash=factual.to_dict().get("hash"),
        metadata={"change_report": change_report},
    )
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
        "duplicate_risk": risk.to_dict(),
        "representation_risk": rep_risk.to_dict(),
        "factual_core": factual.to_dict(),
        "document_quality": quality,
        "answer_sheet": quality.get("answer_sheet"),
        "document_version": {
            "id": doc_version.id,
            "version_number": doc_version.version_number,
            "checksum_sha256": doc_version.checksum_sha256,
        },
    }
    application.state = WorkflowState.PACKET_READY.value
    application.updated_at = datetime.utcnow()
    job.state = WorkflowState.PACKET_READY.value

    db.add(application)
    db.add(job)
    db.commit()
    db.refresh(application)

    from app.config import settings
    from app.services.drive_settings import resolve_active_drive_root

    if settings.oauth_fixture_mode:
        drive_accessible = True
    else:
        _, _, drive_accessible = resolve_active_drive_root(db)
    metadata = application.packet_metadata or {}
    if not drive_accessible:
        metadata["drive_upload_skipped"] = (
            "No accessible Drive root with drive.file scope. Create an app-owned root in Settings."
        )
        application.packet_metadata = metadata
        db.add(application)
        db.commit()
        db.refresh(application)
    else:
        try:
            from app.models import ApplicationDocumentVersion
            from app.services.integrations import get_drive_client

            drive = get_drive_client(db)
            docx_uri = drive.upload_file(str(docx_path), docx_path.name)
            pdf_uri = drive.upload_file(str(pdf_path), pdf_path.name)
            version_row = (
                db.query(ApplicationDocumentVersion)
                .filter(
                    ApplicationDocumentVersion.application_id == application.id,
                    ApplicationDocumentVersion.version_number == version_number,
                )
                .one()
            )
            version_row.drive_docx_id = docx_uri
            version_row.drive_pdf_id = pdf_uri
            db.add(version_row)
            metadata["drive_links"] = {"docx": docx_uri, "pdf": pdf_uri}
            metadata["drive_version"] = {
                "version_number": doc_version.version_number,
                "docx_id": docx_uri,
                "pdf_id": pdf_uri,
            }
            application.packet_metadata = metadata
            db.add(application)
            db.commit()
            db.refresh(application)
        except Exception as exc:
            metadata["drive_upload_error"] = str(exc)[:240]
            application.packet_metadata = metadata
            db.add(application)
            db.commit()
            db.refresh(application)

    record_usage(db, operation="packet_generation", cost_usd=0.5, job_id=job.id)
    record_ledger_from_application(db, application, actor=actor, status=application.state)
    record_timeline_event(
        db,
        application_id=application.id,
        job_id=job.id,
        event_type="packet_generated",
        title="Application packet generated",
        description=f"Version v{doc_version.version_number:02d} created for {job.title} at {job.company}.",
        actor_email=actor,
        metadata={"version_number": doc_version.version_number},
    )
    record_timeline_event(
        db,
        application_id=application.id,
        job_id=job.id,
        event_type="validation_completed",
        title="Document validation completed",
        description="ATS diagnostics and factual-core validation passed.",
        actor_email=actor,
    )
    write_audit(
        db,
        event_type="packet.generated",
        actor=actor,
        resource_type="application",
        resource_id=str(application.id),
        details={"job_id": job.id, "profile": resume_profile, "evidence_count": len(evidence)},
    )
    return application
