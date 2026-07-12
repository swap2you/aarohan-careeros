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


class JobOrigin(str, Enum):
    """Canonical discovery origin category for a job row.

    Distinct from ``data_provenance`` (owner-visibility exclusion of fixture/test) and from
    the lifecycle ``state``. Used to distinguish owner-added opportunities from connector
    records and to power source explainability.
    """

    OWNER_ADDED = "OWNER_ADDED"
    GMAIL_ALERT = "GMAIL_ALERT"
    PUBLIC_CONNECTOR = "PUBLIC_CONNECTOR"
    ATS_BOARD = "ATS_BOARD"
    RECRUITER_MESSAGE = "RECRUITER_MESSAGE"


class ManualOpportunityStatus(str, Enum):
    """Owner-facing tracking status for manual / actively-tracked opportunities."""

    SAVED = "SAVED"
    SHORTLISTED = "SHORTLISTED"
    APPLIED = "APPLIED"
    INTERVIEWING = "INTERVIEWING"
    REJECTED = "REJECTED"
    OFFER = "OFFER"
    CLOSED = "CLOSED"


class DiscoveryPolicyVersion(Base):
    """Versioned owner discovery-policy override stored in PostgreSQL.

    The effective discovery policy = immutable application defaults
    (``config/job-discovery-policy.yml``) deep-merged with the ``overrides`` of the single
    ``active`` version here. Drafts and archived versions are retained for history, audit,
    and rollback. ``overrides`` is validated data only — never executable expressions.
    """

    __tablename__ = "discovery_policy_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, index=True)
    # draft | active | archived
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    preset: Mapped[str | None] = mapped_column(String(16), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    defaults_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    activated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    remember_me: Mapped[bool] = mapped_column(Boolean, default=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


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
    provider_posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_freshness_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    freshness_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    freshness_bucket: Mapped[str | None] = mapped_column(String(32), nullable=True)
    location_eligibility: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    location_eligibility_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_eligibility: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    role_eligibility_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_profile: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    profile_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    matched_title_patterns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ingest_decision: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    ingest_reason_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ingest_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    eligible_for_owner: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
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
    data_provenance: Mapped[str] = mapped_column(String(32), default="live", index=True)
    # Workflow 01.5 — canonical origin classification (see JobOrigin). This is a
    # discovery-provenance category, distinct from data_provenance (which governs owner
    # visibility exclusion of fixture/test rows) and from the lifecycle `state`.
    origin: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    origin_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Manual owner-added opportunity tracking (independent of connector lifecycle `state`).
    added_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    added_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    # When true the row is exempt from automated freshness age-out (owner-added / applied-to).
    manual_protected: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Owner-facing manual tracking status (SAVED/SHORTLISTED/APPLIED/INTERVIEWING/REJECTED/
    # OFFER/CLOSED); see ManualOpportunityStatus. Null for pure connector rows.
    manual_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    score: Mapped["JobScore | None"] = relationship(back_populates="job", uselist=False)
    application: Mapped["Application | None"] = relationship(back_populates="job", uselist=False)
    company_ref: Mapped["Company | None"] = relationship(back_populates="jobs")


class ConnectorRun(Base):
    __tablename__ = "connector_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    search_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    secondary_review_count: Mapped[int] = mapped_column(Integer, default=0)
    quarantined_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    archived_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    live: Mapped[bool] = mapped_column(Boolean, default=True)
    health_state: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    reason_distribution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)


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
        ForeignKey(
            "application_document_versions.id",
            name="fk_applications_submitted_version",
            use_alter=True,
        ),
        nullable=True,
    )
    latest_version_number: Mapped[int] = mapped_column(Integer, default=0)
    data_provenance: Mapped[str] = mapped_column(String(32), default="live")
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
    snippet: Mapped[str | None] = mapped_column(String(512), nullable=True)
    signal_type: Mapped[str] = mapped_column(String(64), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    gmail_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    gmail_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_classification_override: Mapped[str | None] = mapped_column(String(64), nullable=True)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
    interview_rounds: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    negotiation_prep: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    document_links: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recruiter_timeline: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gaps_and_risks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
    message_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(32), default="LEGACY")
    produced_entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    produced_entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    produced_entity_count: Mapped[int] = mapped_column(Integer, default=0)
    last_processing_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    replay_required: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    replay_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GmailIngestReview(Base):
    __tablename__ = "gmail_ingest_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gmail_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gmail_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="quarantined")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ignored_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    recruiter_signal_id: Mapped[int | None] = mapped_column(ForeignKey("recruiter_signals.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    parent_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_provenance: Mapped[str] = mapped_column(String(32), default="live", index=True)
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
