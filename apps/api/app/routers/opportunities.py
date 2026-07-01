from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.services.opportunity_intake import confirm_opportunity, extract_opportunity, recommend_profiles

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


class OpportunityExtractRequest(BaseModel):
    url: str | None = None
    plain_text: str | None = None
    rich_text: str | None = None
    recruiter_email_text: str | None = None
    company: str | None = None
    title: str | None = None
    location: str | None = None
    salary_text: str | None = None
    requisition_id: str | None = None


class OpportunityConfirmRequest(BaseModel):
    extracted: dict
    resume_profile: str | None = None
    generate_packet: bool = False


@router.post("/extract")
def extract(payload: OpportunityExtractRequest, _: User = Depends(get_current_user)) -> dict:
    if not any(
        [
            payload.url,
            payload.plain_text,
            payload.rich_text,
            payload.recruiter_email_text,
            payload.company,
            payload.title,
        ]
    ):
        raise HTTPException(status_code=400, detail="Provide a URL, pasted text, or manual job details.")
    return extract_opportunity(**payload.model_dump())


@router.post("/recommend-profiles")
def recommend(payload: dict, _: User = Depends(get_current_user)) -> dict:
    title = str(payload.get("title") or "")
    description = str(payload.get("description_text") or payload.get("description") or "")
    return {"recommended_profiles": recommend_profiles(title, description)}


@router.post("/confirm")
def confirm(
    payload: OpportunityConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return confirm_opportunity(
            db,
            fields=payload.extracted,
            actor=current_user.email,
            resume_profile=payload.resume_profile,
            generate_packet=payload.generate_packet,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
