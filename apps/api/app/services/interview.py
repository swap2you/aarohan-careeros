from sqlalchemy.orm import Session

from app.models import InterviewPack, Job
from app.services.ai_budget import enforce_budget, record_usage
from app.services.audit import write_audit


def generate_interview_pack(db: Session, job: Job, *, actor: str) -> InterviewPack:
    enforce_budget(db, estimated_cost=2.0, operation="interview_pack")
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
        "automation_api_performance_cicd": [
            "How do you structure REST Assured layers for maintainability?",
            "What CI/CD quality gates would you implement for release confidence?",
            "How do you triage performance regressions under release pressure?",
        ],
        "system_design": [
            "Design a test platform for 30+ microservices with shared fixtures and reporting.",
            "How would you architect an automation framework for web, API, and batch validation?",
        ],
        "ai_qe": [
            "How do you evaluate LLM-assisted test generation quality?",
            "What guardrails would you add for agentic QA workflows?",
            "How would you evaluate RAG quality for internal knowledge bases?",
            "What observability would you require for AI-assisted SDLC workflows?",
        ],
        "leadership": [
            "Tell me about leading a distributed offshore team.",
            "How do you handle conflicting stakeholder priorities?",
            "Describe hiring and interview process design for SDET teams.",
        ],
        "behavioral": [
            "Describe a time you improved release confidence under deadline pressure.",
            "Tell me about a quality transformation with measurable outcomes.",
        ],
    }

    if "data" in text or "database" in text:
        questions.setdefault("data", ["How do you validate data-heavy enterprise workflows?"])
    if "cloud" in text or "aws" in text or "azure" in text:
        questions.setdefault("cloud", ["How do you test cloud-native services and deployment pipelines?"])

    system_design = {
        "scenarios": questions["system_design"],
        "evaluation_criteria": ["scope clarity", "tradeoffs", "operational readiness", "quality governance"],
    }
    answer_rubric = {
        "dimensions": ["technical depth", "leadership", "truthfulness", "structure", "business impact"],
        "scale": "1-5",
        "pass_threshold": 4,
    }
    exercises = {
        "api_automation_design": {
            "prompt": "Draft a REST Assured + CI integration outline for a sample service.",
            "rubric": answer_rubric,
        },
        "flaky_test_triage": {
            "prompt": "Given 20 failing tests, propose a triage workflow.",
            "rubric": answer_rubric,
        },
        "take_home_simulation": {
            "prompt": "Create a 2-hour quality assessment plan for a legacy monolith moving to microservices.",
            "rubric": answer_rubric,
        },
    }

    pack = db.query(InterviewPack).filter(InterviewPack.job_id == job.id).one_or_none() or InterviewPack(job_id=job.id)
    pack.company_briefing = (
        f"{job.company}: research product, quality maturity, engineering blog, recent releases, and leadership priorities."
    )
    pack.role_map = (
        f"Primary outcomes for {job.title}: quality strategy, automation platform, team leadership, release governance."
    )
    pack.gap_analysis = "Map verified evidence to each JD requirement; flag TODO_VERIFY items with honest bridge answers."
    pack.questions = questions
    pack.star_stories = {
        "framework_modernization": "Use verified automation leadership evidence only.",
        "performance_program": "Bridge from JMeter/BlazeMeter experience where applicable.",
        "offshore_leadership": "Use TEAM_LEADERSHIP and MULTI_ROLE_DELIVERY evidence.",
    }
    pack.exercises = exercises
    pack.weak_areas = {"tracked": [], "history": []}
    pack.prep_plan = (
        "Day 1: company research. Day 2: technical refresh. Day 3: leadership STAR stories. "
        "Day 4: AI/QE topics. Day 5: system design. Day 6: mock interview. Day 7: gap review."
    )
    pack.voice_mock_prompt = (
        f"Conduct a 45-minute mock interview for {job.title} at {job.company}. "
        "Focus on QE leadership, automation architecture, AI-enabled quality, and stakeholder communication."
    )
    pack.answer_rubric = answer_rubric
    pack.system_design = system_design

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
