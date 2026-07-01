"""Ensure Playwright e2e admin exists alongside the primary owner admin."""

import os
import sys

from app.database import SessionLocal
from app.models import User
from app.services.auth import hash_password
from app.services.environment import is_e2e_database

E2E_EMAIL = "e2e@test.local"


def main() -> int:
    if not is_e2e_database():
        allow_owner = os.environ.get("ALLOW_E2E_LOGIN_ON_OWNER", "").lower() in {"1", "true", "yes"}
        if not allow_owner:
            print(
                "Refusing to create E2E user on owner database. "
                "Use Start-Aarohan-E2E.ps1 (career_os_e2e on ports 8001/3001).",
                file=sys.stderr,
            )
            return 1
    e2e_password = os.environ.get("E2E_TEST_PASSWORD")
    if not e2e_password:
        print("E2E_TEST_PASSWORD environment variable is required", file=sys.stderr)
        return 1
    db = SessionLocal()
    try:
        row = db.query(User).filter(User.email == E2E_EMAIL).one_or_none()
        hashed = hash_password(e2e_password)
        if row:
            row.hashed_password = hashed
            row.is_admin = True
            row.is_active = True
        else:
            db.add(
                User(
                    email=E2E_EMAIL,
                    hashed_password=hashed,
                    is_admin=True,
                    is_active=True,
                )
            )
        db.commit()
        print(f"OK: e2e user ready ({E2E_EMAIL})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
