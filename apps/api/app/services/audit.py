from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit(
    db: Session,
    *,
    event_type: str,
    actor: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        event_type=event_type,
        actor=actor,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
