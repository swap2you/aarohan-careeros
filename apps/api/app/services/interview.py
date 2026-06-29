"""R2.8 evidence-grounded interview intelligence."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Application, ApplicationDocumentVersion, EvidenceItem, InterviewPack, Job, RecruiterSignal
from app.services.ai_budget import enforce_budget, record_usage
from app.services.audit import write_audit


def _approved_evidence(db: Session) -> list[EvidenceItem]:
    return (
        db.query(EvidenceItem)
        .filter(EvidenceItem.public_use.is_(True), EvidenceItem.status == "USER_CONFIRMED")
        .order_by(EvidenceItem.evidence_id)
        .all()
    )


def _star_stories_from_evidence(items: list[EvidenceItem]) -> dict[str, str]:
    stories: dict[str, str] = {}
    for item in items[:8]:
        stories[item.evidence_id] = item.statement
    if not stories:
        stories["note"] = "No approved public evidence available. Add Career Vault items before external interviews."
    return stories


def _document_links(db: Session, job_id: int) -> dict:
    app = (
        db.query(Application)
        .filter(Application.job_id == job_id)
        .order_by(Application.id.desc())
        .first()
    )
    if not app:
        return {"status": "no_application", "message": "Generate an application packet to link resume and cover letter."}
    version = (
        db.query(ApplicationDocumentVersion)
        .filter(ApplicationDocumentVersion.application_id == app.id)
        .order_by(ApplicationDocumentVersion.version_number.desc())
        .first()
    )
    if not version:
        return {"application_id": app.id, "status": "no_versions"}
    return {
        "application_id": app.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "docx_path": version.docx_path,
        "pdf_path": version.pdf_path,
        "immutable_submitted": version.is_submitted_immutable,
    }


def _recruiter_timeline(db: Session, job: Job) -> list[dict]:
    q = db.query(RecruiterSignal).order_by(RecruiterSignal.received_at.desc())
    rows = q.filter(
        (RecruiterSignal.job_id == job.id)
        | (RecruiterSignal.company_id == job.company_id)
    ).limit(20).all()
    return [
        {
            "id": row.id,
            "signal_type": row.signal_type,
            "sender": row.sender,
            "subject": row.subject,
            "snippet": row.snippet,
            "received_at": row.received_at.isoformat() if row.received_at else None,
        }
        for row in rows
    ]


def generate_interview_pack(db: Session, job: Job, *, actor: str) -> InterviewPack:
    enforce_budget(db, estimated_cost=2.0, operation="interview_pack")
    evidence = _approved_evidence(db)
    text = f"{job.title} {job.description_text}".lower()

    questions = {
        "recruiter_screen": [
            "Walk me through your Quality Engineering leadership experience.",
            "Why this role and company now?",
            "What are your compensation and remote-work expectations?",
        ],
        "hiring_manager": [
            "How do you balance delivery pressure with quality governance?",
            "Describe a framework modernization you led.",
            "How do you measure quality outcomes for leadership stakeholders?",
        ],
        "technical": [
            "Design an API automation strategy for a microservices platform.",
            "How would you reduce flaky tests in CI?",
            "Explain your approach to performance test design and capacity readiness.",
        ],
        "leadership": [
            "Tell me about leading a distributed offshore team.",
            "How do you handle conflicting stakeholder priorities?",
        ],
        "behavioral": [
            "Describe a time you improved release confidence under deadline pressure.",
        ],
    }
    if "data" in text:
        questions["data"] = ["How do you validate data-heavy enterprise workflows?"]
    if "cloud" in text or "aws" in text:
        questions["cloud"] = ["How do you test cloud-native deployment pipelines?"]

    interview_rounds = {
        "rounds": [
            {"name": "Recruiter screen", "focus": "motivation, logistics, compensation range", "status": "planned"},
            {"name": "Hiring manager", "focus": "leadership, delivery, stakeholder alignment", "status": "planned"},
            {"name": "Technical panel", "focus": "architecture, automation, quality strategy", "status": "planned"},
            {"name": "Final", "focus": "culture, executive alignment, close plan", "status": "planned"},
        ]
    }
    negotiation_prep = {
        "research": [
            "Document verified scope and outcomes from approved evidence only.",
            "Clarify base vs bonus vs equity before negotiating.",
            "Prepare questions on quality investment and team size.",
        ],
        "questions_for_them": [
            "What quality metrics matter most in the first 90 days?",
            "How is QE represented in release governance?",
        ],
        "boundaries": "Do not invent compensation history or competing offers.",
    }
    gaps = {
        "verified_strengths": [e.evidence_id for e in evidence[:5]],
        "risks": [
            "Any JD requirement without matching approved evidence should be discussed honestly.",
            "Use bridge answers only when evidence is partial, never fabricated metrics.",
        ],
    }

    pack = db.query(InterviewPack).filter(InterviewPack.job_id == job.id).one_or_none() or InterviewPack(job_id=job.id)
    pack.company_briefing = (
        f"{job.company} — {job.title}. Review public product information, engineering practices, "
        f"and recent releases. Location: {job.location or 'TBD'}."
    )
    pack.role_map = f"Primary outcomes for {job.title}: quality strategy, automation platform, team leadership."
    pack.gap_analysis = "Mapped from approved Career Vault evidence only."
    pack.questions = questions
    pack.star_stories = _star_stories_from_evidence(evidence)
    pack.exercises = {
        "api_automation_design": {"prompt": "Outline REST Assured + CI integration for a sample service."},
        "flaky_test_triage": {"prompt": "Propose triage workflow for failing CI tests."},
    }
    pack.weak_areas = {"tracked": [], "history": []}
    pack.prep_plan = "Research → technical refresh → STAR rehearsal → mock interview → gap review."
    pack.voice_mock_prompt = f"45-minute mock interview for {job.title} at {job.company}."
    pack.answer_rubric = {"dimensions": ["technical depth", "leadership", "truthfulness"], "scale": "1-5"}
    pack.system_design = {"scenarios": ["Design a test platform for microservices at scale."]}
    pack.interview_rounds = interview_rounds
    pack.negotiation_prep = negotiation_prep
    pack.document_links = _document_links(db, job.id)
    pack.recruiter_timeline = _recruiter_timeline(db, job)
    pack.gaps_and_risks = gaps

    db.add(pack)
    db.commit()
    db.refresh(pack)

    record_usage(db, operation="interview_pack", cost_usd=2.0, job_id=job.id)
    write_audit(
        db,
        event_type="interview_pack.generated",
        actor=actor,
        resource_type="interview_pack",
        resource_id=str(pack.id),
        details={"job_id": job.id},
    )
    return pack


def score_exercise(db: Session, pack: InterviewPack, exercise_id: str, scores: dict) -> InterviewPack:
    exercises = pack.exercises or {}
    if exercise_id not in exercises:
        raise ValueError("Unknown exercise")
    weak = pack.weak_areas or {"tracked": [], "history": []}
    avg = sum(scores.values()) / max(len(scores), 1)
    entry = {"exercise_id": exercise_id, "scores": scores, "average": avg}
    weak["history"] = (weak.get("history") or []) + [entry]
    if avg < 4:
        tracked = set(weak.get("tracked") or [])
        tracked.add(exercise_id)
        weak["tracked"] = sorted(tracked)
    pack.weak_areas = weak
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return pack
