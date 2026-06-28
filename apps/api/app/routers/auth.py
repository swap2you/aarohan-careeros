from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import LoginRequest, TokenResponse
from app.services.auth import create_access_token, hash_password, verify_password
from app.services.career_vault import sync_evidence_registry
from app.services.setup import has_admin_user, is_setup_complete, mark_setup_complete

router = APIRouter(prefix="/auth", tags=["auth"])


class SetupRequest(BaseModel):
    email: str
    password: str


@router.get("/setup-status")
def setup_status(db: Session = Depends(get_db)) -> dict:
    return {
        "setup_required": not is_setup_complete(db) and not has_admin_user(db),
        "has_admin": has_admin_user(db),
    }


@router.post("/setup", response_model=TokenResponse)
def setup_admin(payload: SetupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if has_admin_user(db):
        raise HTTPException(status_code=400, detail="Administrator already configured")
    if len(payload.password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")
    user = User(email=payload.email, hashed_password=hash_password(payload.password), is_admin=True)
    db.add(user)
    db.commit()
    mark_setup_complete(db)
    sync_evidence_registry(db)
    return TokenResponse(access_token=create_access_token(user.email))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if not has_admin_user(db):
        raise HTTPException(status_code=403, detail="Setup required")
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.email))


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {"email": current_user.email, "id": current_user.id}


def bootstrap_admin_from_env(db: Session) -> None:
    if has_admin_user(db):
        return
    if settings.admin_email and settings.admin_password and len(settings.admin_password) >= 12:
        user = User(
            email=settings.admin_email,
            hashed_password=hash_password(settings.admin_password),
            is_admin=True,
        )
        db.add(user)
        db.commit()
        mark_setup_complete(db)
