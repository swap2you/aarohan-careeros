from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Application, ApprovalAction, WorkflowState
from app.services.audit import write_audit
from app.services.document_versions import mark_version_submitted
from app.services.duplicate_risk import RiskLevel, evaluate_duplicate_risk, record_ledger_from_application
from app.services.representation import evaluate_representation_risk
from app.services.workflow_timeline import record_timeline_event

ALLOWED_ACTIONS = {
    "approve": WorkflowState.APPROVED_FOR_SUBMISSION,
    "needs_edit": WorkflowState.NEEDS_EDIT,
    "hold": WorkflowState.SECONDARY_REVIEW,
    "reject": WorkflowState.REJECTED,
    "mark_submitted": WorkflowState.SUBMITTED,
    "not_submitted": WorkflowState.NEEDS_EDIT,
    "saved_for_later": WorkflowState.SECONDARY_REVIEW,
    "withdrawn": WorkflowState.CLOSED,
}

EVENT_ONLY_ACTIONS = {"opened_application"}


def apply_approval_action(
    db: Session,
    application: Application,
    *,
    action: str,
    actor_email: str,
    notes: str | None = None,
) -> Application:
    if action not in ALLOWED_ACTIONS and action not in EVENT_ONLY_ACTIONS:
        raise ValueError(f"Unsupported approval action: {action}")

    if action in {"approve", "mark_submitted"}:
        risk = evaluate_duplicate_risk(db, application.job)
        if risk.level == RiskLevel.RED:
            raise ValueError(f"{risk.indicator}: {risk.summary}")
        rep = evaluate_representation_risk(db, application.job)
        if rep.level == RiskLevel.RED:
            raise ValueError(f"{rep.indicator}: {rep.summary}")

    if action == "approve":
        quality = (application.packet_metadata or {}).get("document_quality", {})
        if quality and not quality.get("passed", True):
            raise ValueError("Document validation failed. Fix issues or regenerate before approval.")

    if action in EVENT_ONLY_ACTIONS:
        record_timeline_event(
            db,
            application_id=application.id,
            job_id=application.job_id,
            event_type="application_opened",
            title="Official application opened",
            description=notes or "Opened employer application URL.",
            actor_email=actor_email,
            metadata={"action": action},
        )
        write_audit(
            db,
            event_type="approval.action",
            actor=actor_email,
            resource_type="application",
            resource_id=str(application.id),
            details={"action": action, "event_only": True, "notes": notes},
        )
        db.commit()
        db.refresh(application)
        return application

    new_state = ALLOWED_ACTIONS[action]
    application.state = new_state.value
    application.updated_at = datetime.utcnow()
    if action == "mark_submitted":
        application.submitted_at = datetime.utcnow()
        application.job.state = WorkflowState.SUBMITTED.value
        mark_version_submitted(db, application, actor=actor_email)
        db.add(application.job)

    db.add(
        ApprovalAction(
            application_id=application.id,
            action=action,
            notes=notes,
            actor_email=actor_email,
        )
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    record_ledger_from_application(
        db,
        application,
        actor=actor_email,
        status=application.state,
    )

    timeline_map = {
        "approve": ("approved", "Packet approved for submission", "Approved for manual submission."),
        "reject": ("rejected", "Packet rejected", notes or "Rejected by reviewer."),
        "mark_submitted": ("submitted", "Marked as submitted", "User confirmed submission on employer site."),
        "opened_application": ("application_opened", "Official application opened", "Opened employer application URL."),
        "not_submitted": ("not_submitted", "Not submitted", notes or "User chose not to submit."),
        "saved_for_later": ("saved_for_later", "Saved for later", notes or "Deferred application."),
        "withdrawn": ("withdrawn", "Application withdrawn", notes or "Withdrawn by user."),
    }
    if action in timeline_map:
        event_type, title, description = timeline_map[action]
        record_timeline_event(
            db,
            application_id=application.id,
            job_id=application.job_id,
            event_type=event_type,
            title=title,
            description=description,
            actor_email=actor_email,
            metadata={"action": action, "notes": notes},
        )

    write_audit(
        db,
        event_type="approval.action",
        actor=actor_email,
        resource_type="application",
        resource_id=str(application.id),
        details={"action": action, "new_state": new_state.value, "notes": notes},
    )
    return application
