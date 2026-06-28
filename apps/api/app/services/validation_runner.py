import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import ValidationRun

ROOT = Path(__file__).resolve().parents[4]


def run_local_validation(db: Session, *, actor: str) -> ValidationRun:
    results: dict = {"steps": []}
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
                "stdout": (proc.stdout or "")[-2000:],
                "stderr": (proc.stderr or "")[-2000:],
            }
        )

    step("secret_scan", [sys.executable, "scripts/validation/secret_scan.py"])
    step("prohibited_source_scan", [sys.executable, "scripts/validation/prohibited_source_scan.py"])
    step("pytest", [sys.executable, "-m", "pytest", "-q"], cwd=ROOT / "apps" / "api")

    run = ValidationRun(
        status="PASS" if passed else "FAIL",
        summary=f"Validation {'passed' if passed else 'failed'} with {len(results['steps'])} steps",
        results=results,
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
