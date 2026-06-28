import re
from datetime import datetime
from pathlib import Path

import yaml
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

from app.config import settings


def _vault_root() -> Path:
    return Path(settings.career_vault_root) if Path(settings.career_vault_root).exists() else Path(__file__).resolve().parents[4] / "career_vault"


def load_resume_profile(profile_id: str) -> dict:
    path = _vault_root() / "resume_profiles" / f"{profile_id}.yml"
    if not path.exists():
        raise ValueError(f"Unknown resume profile: {profile_id}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+#./-]{2,}", text.lower())
    stop = {"the", "and", "for", "with", "you", "our", "will", "this", "that", "from", "have", "your"}
    keywords = []
    for token in tokens:
        if token in stop or token in keywords:
            continue
        keywords.append(token)
    return keywords[:40]


def map_keywords_to_evidence(keywords: list[str], evidence: list[str]) -> dict:
    mapping = {}
    for keyword in keywords:
        matches = [line for line in evidence if keyword in line.lower()]
        if matches:
            mapping[keyword] = matches[:2]
    return mapping


def validate_docx_text(path: Path, expected_sections: list[str]) -> dict:
    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs)
    missing = [section for section in expected_sections if section.lower() not in text.lower()]
    return {"extracted_chars": len(text), "missing_sections": missing, "line_count": len(text.splitlines())}


def build_ats_docx(
    *,
    output_path: Path,
    contact: dict,
    profile: dict,
    evidence: list[str],
    job_title: str,
    company: str,
    keyword_mapping: dict,
    missing_warnings: list[str],
) -> dict:
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    title = doc.add_paragraph(contact.get("name", "Candidate"))
    title.runs[0].bold = True
    title.runs[0].font.size = Pt(16)
    doc.add_paragraph(f"{contact.get('email', '')} | {contact.get('linkedin', '')} | {contact.get('website', '')}")
    doc.add_paragraph(contact.get("location", ""))

    doc.add_paragraph("")
    h = doc.add_paragraph("Professional Summary")
    h.runs[0].bold = True
    h.runs[0].font.size = Pt(14)
    doc.add_paragraph(profile.get("summary", "").strip())
    doc.add_paragraph(profile.get("headline", ""))

    doc.add_paragraph("")
    h = doc.add_paragraph("Core Skills")
    h.runs[0].bold = True
    h.runs[0].font.size = Pt(14)
    for keyword, lines in list(keyword_mapping.items())[:12]:
        doc.add_paragraph(keyword, style="List Bullet")

    doc.add_paragraph("")
    h = doc.add_paragraph("Professional Experience")
    h.runs[0].bold = True
    h.runs[0].font.size = Pt(14)
    for line in evidence:
        doc.add_paragraph(line, style="List Bullet")

    if contact.get("certifications"):
        doc.add_paragraph("")
        h = doc.add_paragraph("Certifications")
        h.runs[0].bold = True
        h.runs[0].font.size = Pt(14)
        for cert in contact["certifications"]:
            doc.add_paragraph(f"{cert.get('name')} ({cert.get('date')})", style="List Bullet")

    doc.add_paragraph("")
    h = doc.add_paragraph("Role Target")
    h.runs[0].bold = True
    doc.add_paragraph(f"{job_title} at {company}")

    if missing_warnings:
        doc.add_paragraph("")
        h = doc.add_paragraph("Internal Review Notes (remove before submission)")
        h.runs[0].bold = True
        for warning in missing_warnings:
            doc.add_paragraph(warning, style="List Bullet")

    doc.core_properties.title = f"Resume - {company} - {job_title}"
    doc.core_properties.author = contact.get("name", "Candidate")
    doc.save(output_path)

    checks = validate_docx_text(
        output_path,
        ["Professional Summary", "Professional Experience", "Role Target"],
    )
    checks["page_warning"] = checks["line_count"] > 120
    return checks
