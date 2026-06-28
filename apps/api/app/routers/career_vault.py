from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import EvidenceItem, User
from app.services.career_vault import sync_evidence_registry

router = APIRouter(prefix="/career-vault", tags=["career-vault"])


@router.get("/evidence")
def list_evidence(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    rows = db.query(EvidenceItem).order_by(EvidenceItem.evidence_id).all()
    return [
        {
            "evidence_id": row.evidence_id,
            "category": row.category,
            "statement": row.statement,
            "status": row.status,
            "public_use": row.public_use,
        }
        for row in rows
    ]


@router.post("/sync")
def sync_vault(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    count = sync_evidence_registry(db)
    return {"synced": count}
