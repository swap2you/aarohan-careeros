from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkflowState(str, Enum):
    NEW = "NEW"
    INGESTED = "INGESTED"
    NORMALIZED = "NORMALIZED"
    REJECTED = "REJECTED"
    SECONDARY_REVIEW = "SECONDARY_REVIEW"
    SHORTLISTED = "SHORTLISTED"
    PACKET_GENERATING = "PACKET_GENERATING"
    PACKET_READY = "PACKET_READY"
    NEEDS_EDIT = "NEEDS_EDIT"
    APPROVED_FOR_SUBMISSION = "APPROVED_FOR_SUBMISSION"
    SUBMITTED = "SUBMITTED"
    FOLLOW_UP_DUE = "FOLLOW_UP_DUE"
    RECRUITER_SIGNAL = "RECRUITER_SIGNAL"
    INTERVIEW_SIGNAL = "INTERVIEW_SIGNAL"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"
    OFFER = "OFFER"
    REJECTED_BY_EMPLOYER = "REJECTED_BY_EMPLOYER"
    CLOSED = "CLOSED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    service: Mapped[str] = mapped_column(String(64), index=True)
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_token: Mapped[str] = mapped_column(Text)
    scopes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_job_source_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str] = mapped_column(String(255), index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workplace_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(8), default="USD")
    description_html: Mapped[str] = mapped_column(Text)
    description_text: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1024))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    freshness_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(512), index=True)
    state: Mapped[str] = mapped_column(String(64), default=WorkflowState.INGESTED.value, index=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    requisition_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    ats_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    normalized_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    role_family: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    match_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    score: Mapped["JobScore | None"] = relationship(back_populates="job", uselist=False)
    application: Mapped["Application | None"] = relationship(back_populates="job", uselist=False)
    company_ref: Mapped["Company | None"] = relationship(back_populates="jobs")


class JobScore(Base):
    __tablename__ = "job_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True)
    total_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    compensation_score: Mapped[float] = mapped_column(Float, default=0.0)
    remote_score: Mapped[float] = mapped_column(Float, default=0.0)
    technical_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    leadership_score: Mapped[float] = mapped_column(Float, default=0.0)
    ai_alignment_score: Mapped[float] = mapped_column(Float, default=0.0)
    stability_score: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    fit_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    gap_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    stability_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trust_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    trust_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    fit_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    hard_filter_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hard_filter_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    match_card: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[Job] = relationship(back_populates="score")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True)
    state: Mapped[str] = mapped_column(String(64), default=WorkflowState.SHORTLISTED.value, index=True)
    resume_docx_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    resume_pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    resume_profile: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    recruiter_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    fit_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    packet_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    drive_folder_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("application_document_versions.id"), nullable=True
    )
    latest_version_number: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job: Mapped[Job] = relationship(back_populates="application")
    approvals: Mapped[list["ApprovalAction"]] = relationship(back_populates="application")
    document_versions: Mapped[list["ApplicationDocumentVersion"]] = relationship(
        back_populates="application",
        foreign_keys="ApplicationDocumentVersion.application_id",
    )
    submitted_version: Mapped["ApplicationDocumentVersion | None"] = relationship(
        foreign_keys=[submitted_version_id],
        post_update=True,
    )
    timeline_events: Mapped[list["ApplicationTimelineEvent"]] = relationship(back_populates="application")


class ApprovalAction(Base):
    __tablename__ = "approval_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped[Application] = relationship(back_populates="approvals")


class RecruiterSignal(Base):
    __tablename__ = "recruiter_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body_text: Mapped[str] = mapped_column(Text)
    signal_type: Mapped[str] = mapped_column(String(64), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)


class InterviewPack(Base):
    __tablename__ = "interview_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    company_briefing: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_map: Mapped[str | None] = mapped_column(Text, nullable=True)
    gap_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    questions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    star_stories: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    exercises: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    weak_areas: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    prep_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_mock_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_rubric: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    system_design: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConsultingLead(Base):
    __tablename__ = "consulting_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company: Mapped[str] = mapped_column(String(255), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    problem_summary: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(64), default="NEW", index=True)
    recommended_service: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proposal_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    lead_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    case_study_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    follow_up_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(64))
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64))
    public_use: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_needed: Mapped[list | None] = mapped_column(JSON, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AIUsageRecord(Base):
    __tablename__ = "ai_usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation: Mapped[str] = mapped_column(String(128), index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ProcessedGmailMessage(Base):
    __tablename__ = "processed_gmail_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    parent_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    aliases: Mapped[list["CompanyAlias"]] = relationship(back_populates="company")
    domains: Mapped[list["CompanyDomain"]] = relationship(back_populates="company")
    jobs: Mapped[list["Job"]] = relationship(back_populates="company_ref")
    ledger_entries: Mapped[list["ApplicationLedger"]] = relationship(back_populates="company")


class CompanyAlias(Base):
    __tablename__ = "company_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    alias: Mapped[str] = mapped_column(String(255))
    normalized_alias: Mapped[str] = mapped_column(String(255), index=True)

    company: Mapped[Company] = relationship(back_populates="aliases")


class CompanyDomain(Base):
    __tablename__ = "company_domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    company: Mapped[Company] = relationship(back_populates="domains")


class CompanyAtsIdentity(Base):
    __tablename__ = "company_ats_identities"
    __table_args__ = (UniqueConstraint("ats_type", "board_token", name="uq_ats_type_board"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    ats_type: Mapped[str] = mapped_column(String(64))
    board_token: Mapped[str] = mapped_column(String(255))


class ApplicationLedger(Base):
    __tablename__ = "application_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
    requisition_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    ats_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    application_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
    normalized_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vendor_channel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company: Mapped[Company] = relationship(back_populates="ledger_entries")
    events: Mapped[list["ApplicationEvent"]] = relationship(back_populates="ledger")


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("application_ledger.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    actor_email: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ledger: Mapped[ApplicationLedger] = relationship(back_populates="events")


class DuplicateOverride(Base):
    __tablename__ = "duplicate_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("application_ledger.id"), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    actor_email: Mapped[str] = mapped_column(String(255))
    policy_version: Mapped[str] = mapped_column(String(32))
    matched_records: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApplicationDocumentVersion(Base):
    __tablename__ = "application_document_versions"
    __table_args__ = (UniqueConstraint("application_id", "version_number", name="uq_app_doc_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    docx_path: Mapped[str] = mapped_column(String(1024))
    pdf_path: Mapped[str] = mapped_column(String(1024))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    drive_docx_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_pdf_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    factual_core_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approval_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_submitted_immutable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped[Application] = relationship(
        back_populates="document_versions",
        foreign_keys=[application_id],
    )


class RepresentationRecord(Base):
    __tablename__ = "representation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_name: Mapped[str] = mapped_column(String(255), index=True)
    client_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    client_name: Mapped[str] = mapped_column(String(255))
    normalized_client: Mapped[str] = mapped_column(String(255), index=True)
    requisition_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    role_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    submission_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    representation_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    representation_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    recruiter_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    no_agreement_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RepresentationOverride(Base):
    __tablename__ = "representation_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    representation_id: Mapped[int | None] = mapped_column(ForeignKey("representation_records.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    actor_email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApplicationTimelineEvent(Base):
    __tablename__ = "application_timeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped[Application] = relationship(back_populates="timeline_events")
