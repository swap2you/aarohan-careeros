from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.models import EvidenceItem


def sync_evidence_registry(db: Session, vault_root: Path | None = None) -> int:
    root = vault_root or Path(__file__).resolve().parents[4] / "career_vault"
    registry_path = root / "evidence_registry.yml"
    if not registry_path.exists():
        return 0

    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    count = 0
    for item in data.get("evidence", []):
        existing = (
            db.query(EvidenceItem)
            .filter(EvidenceItem.evidence_id == item["id"])
            .one_or_none()
        )
        if existing:
            existing.category = item["category"]
            existing.statement = item["statement"]
            existing.status = item["status"]
            existing.public_use = bool(item.get("public_use", False))
            existing.verification_needed = item.get("verification_needed")
        else:
            db.add(
                EvidenceItem(
                    evidence_id=item["id"],
                    category=item["category"],
                    statement=item["statement"],
                    status=item["status"],
                    public_use=bool(item.get("public_use", False)),
                    verification_needed=item.get("verification_needed"),
                )
            )
        count += 1
    db.commit()
    return count


def public_evidence_statements(db: Session) -> list[str]:
    rows = db.query(EvidenceItem).filter(EvidenceItem.public_use.is_(True)).all()
    return [row.statement for row in rows]
