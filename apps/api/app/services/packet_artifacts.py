"""Application packet artifact manifest for UI."""

from __future__ import annotations

from pathlib import Path

from app.models import Application


def list_packet_artifacts(application: Application) -> list[dict]:
    version = application.latest_version_number or 1
    vlabel = f"v{version:02d}"
    meta = application.packet_metadata or {}
    quality = meta.get("document_quality") or {}
    generated_at = application.updated_at.isoformat() if application.updated_at else None

    artifacts: list[dict] = [
        {
            "id": "resume",
            "type": "resume",
            "label": f"Tailored Resume - {vlabel}",
            "formats": ["docx", "pdf"],
            "local_docx": application.resume_docx_path,
            "local_pdf": application.resume_pdf_path,
            "validation_passed": quality.get("passed"),
            "generated_at": generated_at,
            "external": True,
        },
        {
            "id": "cover_letter",
            "type": "cover_letter",
            "label": f"Cover Letter - {vlabel}",
            "formats": ["preview"],
            "preview_text": application.cover_letter,
            "validation_passed": bool(application.cover_letter),
            "generated_at": generated_at,
            "external": True,
        },
        {
            "id": "answer_sheet",
            "type": "answer_sheet",
            "label": f"Application Answer Sheet - {vlabel}",
            "formats": ["preview"],
            "preview_text": meta.get("answer_sheet"),
            "validation_passed": bool(meta.get("answer_sheet")),
            "generated_at": generated_at,
            "external": True,
        },
        {
            "id": "recruiter_note",
            "type": "recruiter_note",
            "label": f"Recruiter Note - {vlabel}",
            "formats": ["preview"],
            "preview_text": application.recruiter_note,
            "validation_passed": bool(application.recruiter_note),
            "generated_at": generated_at,
            "external": False,
        },
        {
            "id": "fit_analysis",
            "type": "fit_analysis",
            "label": f"Fit and Gap Analysis - {vlabel}",
            "formats": ["preview"],
            "preview_text": application.fit_analysis,
            "validation_passed": bool(application.fit_analysis),
            "generated_at": generated_at,
            "external": False,
        },
        {
            "id": "validation_report",
            "type": "validation_report",
            "label": f"Document Validation Report - {vlabel}",
            "formats": ["preview"],
            "preview_text": quality.get("plain_summary") or str(quality.get("ats_diagnostics", {})),
            "validation_passed": quality.get("passed"),
            "generated_at": generated_at,
            "external": False,
        },
    ]

    drive_links = meta.get("drive_links") or {}
    for artifact in artifacts:
        if artifact["id"] == "resume":
            artifact["drive_docx"] = drive_links.get("docx")
            artifact["drive_pdf"] = drive_links.get("pdf")
        local_path = artifact.get("local_docx") or artifact.get("local_pdf")
        artifact["local_exists"] = bool(local_path and Path(str(local_path)).exists())

    submission_ready = [a for a in artifacts if a.get("external")]
    all_external_pass = all(a.get("validation_passed") for a in submission_ready if a.get("validation_passed") is not None)

    return {
        "application_id": application.id,
        "version": version,
        "version_label": vlabel,
        "profile": application.resume_profile,
        "artifacts": artifacts,
        "submission_artifacts": [a["label"] for a in submission_ready],
        "approval_blocked": not all_external_pass or not quality.get("passed", False),
        "approval_block_reason": None if quality.get("passed") else "Document quality validation did not pass.",
    }
