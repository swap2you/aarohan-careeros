"""R2.6.1 database-backed application sessions."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import User, UserSession

SESSION_COOKIE_NAME = "careeros_session"
REMEMBER_ME_DAYS = 60
SHORT_SESSION_HOURS = 12
SLIDING_RENEWAL_DAYS = 60


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_session(
    db: Session,
    user: User,
    *,
    remember_me: bool,
    user_agent: str | None = None,
) -> tuple[str, UserSession]:
    raw_token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    expires_at = (
        now + timedelta(days=REMEMBER_ME_DAYS)
        if remember_me
        else now + timedelta(hours=SHORT_SESSION_HOURS)
    )
    row = UserSession(
        user_id=user.id,
        session_token_hash=hash_session_token(raw_token),
        remember_me=remember_me,
        user_agent=(user_agent or "")[:512] or None,
        created_at=now,
        last_used_at=now,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return raw_token, row


def get_user_for_session_token(db: Session, raw_token: str | None) -> User | None:
    if not raw_token:
        return None
    token_hash = hash_session_token(raw_token)
    row = (
        db.query(UserSession)
        .filter(
            UserSession.session_token_hash == token_hash,
            UserSession.revoked_at.is_(None),
        )
        .one_or_none()
    )
    if not row:
        return None
    now = datetime.utcnow()
    if row.expires_at <= now:
        row.revoked_at = now
        db.add(row)
        db.commit()
        return None

    row.last_used_at = now
    if row.remember_me:
        row.expires_at = now + timedelta(days=SLIDING_RENEWAL_DAYS)
    db.add(row)
    db.commit()

    return (
        db.query(User)
        .filter(User.id == row.user_id, User.is_active.is_(True))
        .one_or_none()
    )


def revoke_session_token(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    token_hash = hash_session_token(raw_token)
    row = db.query(UserSession).filter(UserSession.session_token_hash == token_hash).one_or_none()
    if row and row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        db.add(row)
        db.commit()


def revoke_all_user_sessions(db: Session, user_id: int) -> int:
    now = datetime.utcnow()
    rows = (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .all()
    )
    for row in rows:
        row.revoked_at = now
        db.add(row)
    db.commit()
    return len(rows)


def cleanup_expired_sessions(db: Session) -> int:
    now = datetime.utcnow()
    rows = (
        db.query(UserSession)
        .filter(UserSession.revoked_at.is_(None), UserSession.expires_at <= now)
        .all()
    )
    for row in rows:
        row.revoked_at = now
        db.add(row)
    db.commit()
    return len(rows)
