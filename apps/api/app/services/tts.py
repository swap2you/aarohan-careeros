"""R2.9 OpenAI TTS with local fallback."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.services.ai_budget import record_usage
from app.services.audit import write_audit


def synthesize_speech(
    db: Session,
    text: str,
    *,
    voice: str = "alloy",
    actor: str,
) -> dict:
    digest = hashlib.sha256(f"{voice}:{text}".encode()).hexdigest()[:16]
    out_dir = Path(settings.generated_root) / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"tts_{digest}.mp3"

    if out_path.exists():
        return {"mode": "cache", "path": str(out_path), "mime": "audio/mpeg"}

    if not settings.ai_api_key:
        return {
            "mode": "unavailable",
            "message": "OpenAI API key not configured. Display text only.",
            "text_preview": text[:500],
        }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
            json={"model": settings.openai_tts_model, "voice": voice, "input": text[:4096]},
        )
    if response.status_code != 200:
        return {"mode": "error", "message": "TTS request failed", "text_preview": text[:500]}

    out_path.write_bytes(response.content)
    record_usage(db, operation="tts", cost_usd=0.02)
    write_audit(db, event_type="tts.generated", actor=actor, resource_type="tts", resource_id=digest)
    return {"mode": "generated", "path": str(out_path), "mime": "audio/mpeg"}
