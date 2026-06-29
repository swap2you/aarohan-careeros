import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import ValidationRun
from app.services.live_validation import run_live_owner_validation


def _repo_root() -> Path:
    path = Path(__file__).resolve()
    if len(path.parents) > 4 and (path.parents[4] / "scripts").exists():
        return path.parents[4]
    return path.parents[2]


ROOT = _repo_root()


def run_local_validation(db: Session, *, actor: str) -> ValidationRun:
    if not settings.oauth_fixture_mode:
        return run_live_owner_validation(db, actor=actor)

    results: dict = {"steps": [], "mode": "automated_fixture"}
    passed = True

    def step(name: str, cmd: list[str], cwd: Path | None = None) -> None:
        nonlocal passed
        proc = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True)
        ok = proc.returncode == 0
        if not ok:
            passed = False
        results["steps"].append(
            {
                "name": name,
                "ok": ok,
                "status": "PASS" if ok else "FAIL",
                "summary": f"{name} {'passed' if ok else 'failed'}",
                "stderr": (proc.stderr or "")[-500:],
            }
        )

    step("secret_scan", [sys.executable, "scripts/validation/secret_scan.py"])
    step("prohibited_source_scan", [sys.executable, "scripts/validation/prohibited_source_scan.py"])

    run = ValidationRun(
        status="PASS" if passed else "FAIL",
        summary="; ".join(f"{s['name']}: {s['status']}" for s in results["steps"]),
        results=results,
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
