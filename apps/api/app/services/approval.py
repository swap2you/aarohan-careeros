from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Application, ApprovalAction, WorkflowState
from app.services.audit import write_audit
from app.services.duplicate_risk import RiskLevel, evaluate_duplicate_risk, record_ledger_from_application

ALLOWED_ACTIONS = {
    "approve": WorkflowState.APPROVED_FOR_SUBMISSION,
    "needs_edit": WorkflowState.NEEDS_EDIT,
    "hold": WorkflowState.SECONDARY_REVIEW,
    "reject": WorkflowState.REJECTED,
    "mark_submitted": WorkflowState.SUBMITTED,
}


def apply_approval_action(
    db: Session,
    application: Application,
    *,
    action: str,
    actor_email: str,
    notes: str | None = None,
) -> Application:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported approval action: {action}")

    if action in {"approve", "mark_submitted"}:
        risk = evaluate_duplicate_risk(db, application.job)
        if risk.level == RiskLevel.RED:
            raise ValueError(f"{risk.indicator}: {risk.summary}")

    new_state = ALLOWED_ACTIONS[action]
    application.state = new_state.value
    application.updated_at = datetime.utcnow()
    if action == "mark_submitted":
        application.submitted_at = datetime.utcnow()
        application.job.state = WorkflowState.SUBMITTED.value
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

    write_audit(
        db,
        event_type="approval.action",
        actor=actor_email,
        resource_type="application",
        resource_id=str(application.id),
        details={"action": action, "new_state": new_state.value, "notes": notes},
    )
    return application
