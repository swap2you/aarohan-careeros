from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import ConsultingLead, User
from app.schemas import ConsultingLeadOut, ConsultingLeadRequest
from app.services.consulting import SERVICE_CATALOG, create_consulting_lead

router = APIRouter(prefix="/consulting", tags=["consulting"])


@router.get("/services")
def list_services(_: User = Depends(get_current_user)) -> dict:
    return {"services": SERVICE_CATALOG}


@router.get("/leads", response_model=list[ConsultingLeadOut])
def list_leads(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ConsultingLead]:
    return db.query(ConsultingLead).order_by(ConsultingLead.created_at.desc()).all()


@router.post("/leads", response_model=ConsultingLeadOut)
def create_lead(
    payload: ConsultingLeadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsultingLead:
    return create_consulting_lead(db, payload.model_dump(), actor=current_user.email)
