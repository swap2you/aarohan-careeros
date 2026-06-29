from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.services.auth import ALGORITHM
from app.services.sessions import SESSION_COOKIE_NAME, get_user_for_session_token

security = HTTPBearer(auto_error=False)


def _user_from_bearer(credentials: HTTPAuthorizationCredentials | None, db: Session) -> User | None:
    if credentials is None:
        return None
    user = get_user_for_session_token(db, credentials.credentials)
    if user:
        return user
    try:
        payload = jwt.decode(credentials.credentials, settings.app_secret, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        return None
    if not email:
        return None
    return db.query(User).filter(User.email == email, User.is_active.is_(True)).one_or_none()


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
    careeros_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> User:
    user = get_user_for_session_token(db, careeros_session)
    if user:
        return user

    user = _user_from_bearer(credentials, db)
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expired or invalid",
        headers={"X-Aarohan-Auth": "session-required"},
    )


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
    careeros_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> User | None:
    user = get_user_for_session_token(db, careeros_session)
    if user:
        return user
    return _user_from_bearer(credentials, db)
