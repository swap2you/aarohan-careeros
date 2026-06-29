from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.services.ask_aarohan import answer_question
from app.services.tts import synthesize_speech

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    voice: str = "alloy"


@router.post("/ask")
def ask_aarohan(
    payload: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return answer_question(db, payload.question, actor=current_user.email)


@router.post("/tts")
def text_to_speech(
    payload: TtsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return synthesize_speech(db, payload.text, voice=payload.voice, actor=current_user.email)


@router.get("/tts/file/{digest}")
def get_tts_file(
    digest: str,
    _: User = Depends(get_current_user),
):
    path = Path(settings.generated_root) / "tts" / f"tts_{digest}.mp3"
    if not path.exists():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path, media_type="audio/mpeg")
