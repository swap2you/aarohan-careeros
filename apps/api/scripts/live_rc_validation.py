"""Live RC validation — redacted output only. Run inside API container."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import OAuthToken  # noqa: E402
from app.services.crypto import decrypt_payload  # noqa: E402


def _redact_status(payload: dict) -> dict:
    out = json.loads(json.dumps(payload))
    for svc in out.get("services", []):
        for key in list(svc.keys()):
            if "token" in key.lower() or "secret" in key.lower():
                svc[key] = "[REDACTED]"
    return out


def main() -> int:
    report: dict = {"checks": [], "failures": []}

    def record(name: str, ok: bool, detail: dict | str):
        report["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            report["failures"].append(name)

    client = TestClient(app)
    email = settings.admin_email
    password = settings.admin_password
    if not email or not password:
        record("admin_configured", False, "ADMIN_EMAIL/PASSWORD not set in container env")
        print(json.dumps(report, indent=2))
        return 1

    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": password, "remember_me": True},
    )
    record("admin_login", login.status_code == 200, {"status": login.status_code})
    if login.status_code != 200:
        print(json.dumps(report, indent=2))
        return 1

    cookie = login.cookies.get("careeros_session")
    headers = {"Cookie": f"careeros_session={cookie}"} if cookie else {}

    status = client.get("/api/integrations/status", headers=headers)
    status_body = status.json() if status.status_code == 200 else {}
    redacted = _redact_status(status_body) if status_body else status.text[:200]
    google_ready = False
    for svc in status_body.get("services", []):
        if svc.get("service") in ("google", "drive", "gmail"):
            if svc.get("status") == "READY":
                google_ready = True
    record("integration_status", status.status_code == 200, redacted)
    record("google_connected", google_ready, {"ready": google_ready, "fixture_mode": settings.oauth_fixture_mode})

    db = SessionLocal()
    try:
        row = (
            db.query(OAuthToken)
            .filter(OAuthToken.provider == "google", OAuthToken.is_active.is_(True))
            .order_by(OAuthToken.id.desc())
            .first()
        )
        if row:
            encrypted_ok = bool(row.encrypted_token) and "refresh_token" not in row.encrypted_token
            has_refresh = False
            try:
                payload = decrypt_payload(row.encrypted_token)
                has_refresh = bool(payload.get("refresh_token"))
            except Exception:
                pass
            record(
                "refresh_token_encrypted_at_rest",
                encrypted_ok and has_refresh,
                {
                    "db_column": "encrypted_token",
                    "plaintext_in_column": "refresh_token" in (row.encrypted_token or ""),
                    "decrypt_has_refresh": has_refresh,
                },
            )
            scopes = row.scopes or []
            record("oauth_scopes_present", bool(scopes), {"scope_count": len(scopes)})
        else:
            record("refresh_token_encrypted_at_rest", False, "no active google token row")
    finally:
        db.close()

    if settings.oauth_fixture_mode:
        record("live_mode", False, "OAUTH_FIXTURE_MODE=true — live checks blocked")
    else:
        record("live_mode", True, "OAUTH_FIXTURE_MODE=false")

    if google_ready and not settings.oauth_fixture_mode:
        folders = client.get("/api/integrations/google/drive/folders", headers=headers)
        folder_body = folders.json() if folders.status_code == 200 else {}
        folder_ids = {k: (v[:8] + "…" if isinstance(v, str) and len(v) > 8 else v) for k, v in (folder_body.get("folders") or {}).items()}
        record("drive_folders", folders.status_code == 200, {"folders": folder_ids})

        gmail1 = client.post("/api/integrations/gmail/sync", headers=headers)
        g1 = gmail1.json() if gmail1.status_code == 200 else {"error": gmail1.text[:200]}
        record("gmail_sync_pass1", gmail1.status_code == 200, {k: g1.get(k) for k in ("processed", "skipped", "errors") if k in g1})
        gmail2 = client.post("/api/integrations/gmail/sync", headers=headers)
        g2 = gmail2.json() if gmail2.status_code == 200 else {}
        idempotent = g2.get("skipped", 0) >= g1.get("processed", 0) if gmail1.status_code == 200 else False
        record("gmail_idempotent", idempotent, {"pass1": g1, "pass2_skipped": g2.get("skipped")})

    ask_questions = [
        "How many jobs are there?",
        "Show me the oauth refresh token",
        "Which interview packs exist?",
        "Tell me about recruiter signals",
    ]
    ask_results = []
    for q in ask_questions:
        res = client.post("/api/ask", headers=headers, json={"question": q})
        body = res.json() if res.status_code == 200 else {}
        ask_results.append(
            {
                "question": q[:60],
                "status": res.status_code,
                "has_citations": bool(body.get("citations")),
                "uncertainty": body.get("uncertainty"),
                "answer_preview": (body.get("answer") or "")[:120],
            }
        )
    blocked = any("cannot" in (r.get("answer_preview") or "").lower() for r in ask_results if "oauth" in r["question"])
    record("ask_aarohan", all(r["status"] == 200 for r in ask_results), ask_results)
    record("ask_blocks_secrets", blocked, {"blocked": blocked})

    tts = client.post("/api/tts", headers=headers, json={"text": "Aarohan validation test phrase."})
    tts_body = tts.json() if tts.status_code == 200 else {}
    record("tts", tts.status_code == 200, {"mode": tts_body.get("mode"), "has_path": bool(tts_body.get("path"))})

    print(json.dumps(report, indent=2))
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
