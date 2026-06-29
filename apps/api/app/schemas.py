from datetime import datetime

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str | None = None
    remember_me: bool | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class JobIngestRequest(BaseModel):
    source: str
    external_id: str
    title: str
    company: str
    url: str
    location: str | None = None
    workplace_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_text: str | None = None
    description_html: str = ""
    description_text: str | None = None
    posted_at: datetime | str | None = None
    requisition_id: str | None = None
    ats_job_id: str | None = None


class JobScoreOut(BaseModel):
    total_score: float
    compensation_score: float
    remote_score: float
    technical_fit_score: float
    leadership_score: float
    ai_alignment_score: float
    stability_score: float
    evidence_score: float
    fit_analysis: str | None = None
    gap_analysis: str | None = None
    stability_analysis: str | None = None
    recommendation: str | None = None
    trust_score: float | None = None
    trust_reasons: list[str] | None = None
    fit_reasons: list[str] | None = None
    hard_filter_passed: bool | None = None
    hard_filter_reasons: list[str] | None = None
    match_card: dict | None = None

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: int
    source: str
    external_id: str
    title: str
    company: str
    location: str | None
    workplace_type: str | None
    salary_min: int | None
    salary_max: int | None
    url: str
    state: str
    discovered_at: datetime
    posted_at: datetime | None = None
    description_text: str | None = None
    role_family: str | None = None
    is_expired: bool = False
    source_verified: bool = False
    match_summary: str | None = None
    data_provenance: str = "live"
    score: JobScoreOut | None = None

    model_config = {"from_attributes": True}


class ApplicationOut(BaseModel):
    id: int
    job_id: int
    state: str
    cover_letter: str | None
    recruiter_note: str | None
    resume_docx_path: str | None
    resume_pdf_path: str | None
    packet_metadata: dict | None = None
    submitted_at: datetime | None

    model_config = {"from_attributes": True}


class ApprovalRequest(BaseModel):
    action: str = Field(description="approve|needs_edit|hold|reject|mark_submitted")
    notes: str | None = None


class ConsultingLeadRequest(BaseModel):
    company: str
    problem_summary: str
    contact_name: str | None = None
    contact_email: str | None = None


class ConsultingLeadOut(BaseModel):
    id: int
    company: str
    state: str
    recommended_service: str | None
    proposal_draft: str | None

    model_config = {"from_attributes": True}


class RecruiterSignalRequest(BaseModel):
    source: str = "gmail"
    sender: str | None = None
    subject: str | None = None
    body_text: str
    job_id: int | None = None
    gmail_message_id: str | None = None


class InterviewPackOut(BaseModel):
    id: int
    job_id: int
    company_briefing: str | None
    role_map: str | None
    gap_analysis: str | None
    questions: dict | None
    star_stories: dict | None
    exercises: dict | None
    weak_areas: dict | None
    prep_plan: str | None
    voice_mock_prompt: str | None
    answer_rubric: dict | None
    system_design: dict | None
    interview_rounds: dict | None = None
    negotiation_prep: dict | None = None
    document_links: dict | None = None
    recruiter_timeline: list | dict | None = None
    gaps_and_risks: dict | None = None

    model_config = {"from_attributes": True}


class AnalyticsOut(BaseModel):
    total_jobs: int
    shortlisted_jobs: int
    applications_ready: int
    submitted_applications: int
    consulting_leads: int
    interview_packs: int


class AuditLogOut(BaseModel):
    id: int
    event_type: str
    actor: str | None
    resource_type: str | None
    resource_id: str | None
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
