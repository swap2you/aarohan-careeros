from datetime import datetime

from sqlalchemy.orm import Session

from app.models import SystemSetting


SETUP_COMPLETE_KEY = "setup_complete"


def is_setup_complete(db: Session) -> bool:
    row = db.query(SystemSetting).filter(SystemSetting.key == SETUP_COMPLETE_KEY).one_or_none()
    return bool(row and row.value == "true")


def mark_setup_complete(db: Session) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == SETUP_COMPLETE_KEY).one_or_none()
    if row:
        row.value = "true"
        row.updated_at = datetime.utcnow()
    else:
        db.add(SystemSetting(key=SETUP_COMPLETE_KEY, value="true"))
    db.commit()


def has_admin_user(db: Session) -> bool:
    from app.models import User

    return db.query(User).count() > 0
