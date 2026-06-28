from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import ConsultingLead
from app.services.audit import write_audit

SERVICE_CATALOG = [
    "AI-Assisted Quality Engineering Assessment",
    "Automation Framework Modernization",
    "API Automation Accelerator",
    "Performance and Capacity Readiness Assessment",
    "Flaky Test Reduction Program",
    "CI/CD Quality Gate Implementation",
    "LLM and Agent Evaluation Strategy",
    "Test Platform Architecture",
    "Fractional Quality Engineering Leadership",
    "SDET Hiring and Interview Process Design",
]

CASE_STUDIES = {
    "Automation Framework Modernization": "Enterprise automation stabilization and framework modernization.",
    "Flaky Test Reduction Program": "CI pipeline reliability improvement with triage workflow.",
    "LLM and Agent Evaluation Strategy": "AI-assisted SDLC quality controls and evaluation design.",
}


def recommend_service(problem_summary: str) -> str:
    lowered = problem_summary.lower()
    if "flaky" in lowered:
        return "Flaky Test Reduction Program"
    if "performance" in lowered or "load" in lowered:
        return "Performance and Capacity Readiness Assessment"
    if "ci/cd" in lowered or "pipeline" in lowered:
        return "CI/CD Quality Gate Implementation"
    if "llm" in lowered or "agent" in lowered or "genai" in lowered:
        return "LLM and Agent Evaluation Strategy"
    if "automation" in lowered or "framework" in lowered:
        return "Automation Framework Modernization"
    if "api" in lowered:
        return "API Automation Accelerator"
    if "platform" in lowered:
        return "Test Platform Architecture"
    return "AI-Assisted Quality Engineering Assessment"


def score_lead(problem_summary: str, company: str) -> float:
    score = 50.0
    lowered = problem_summary.lower()
    if any(k in lowered for k in ["automation", "quality", "testing", "ci/cd", "performance", "flaky"]):
        score += 20
    if any(k in lowered for k in ["director", "vp", "head", "lead", "manager"]):
        score += 10
    if len(company.strip()) > 2:
        score += 5
    return min(score, 100.0)


def create_consulting_lead(db: Session, payload: dict, *, actor: str) -> ConsultingLead:
    service = recommend_service(payload["problem_summary"])
    lead_score = score_lead(payload["problem_summary"], payload["company"])
    case_study = CASE_STUDIES.get(service, "General QE transformation case study (sanitized).")
    proposal = (
        f"Proposal draft for {payload['company']}:\n"
        f"Recommended service: {service}\n"
        f"Lead score: {lead_score:.0f}/100\n"
        f"Problem: {payload['problem_summary']}\n"
        f"Matched case study: {case_study}\n"
        "Next step: discovery call and scoped assessment.\n"
        "No automatic outreach will be sent."
    )
    lead = ConsultingLead(
        company=payload["company"],
        contact_name=payload.get("contact_name"),
        contact_email=payload.get("contact_email"),
        problem_summary=payload["problem_summary"],
        recommended_service=service,
        proposal_draft=proposal,
        lead_score=lead_score,
        case_study_mapping={"service": service, "case_study": case_study},
        follow_up_status="NEW",
        follow_up_at=datetime.utcnow() + timedelta(days=3),
        state="QUALIFIED" if lead_score >= 70 else "REVIEW",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    write_audit(
        db,
        event_type="consulting.lead_created",
        actor=actor,
        resource_type="consulting_lead",
        resource_id=str(lead.id),
        details={"company": lead.company, "service": service, "lead_score": lead_score},
    )
    return lead
