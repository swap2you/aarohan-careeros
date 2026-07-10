"""Deployment environment detection — owner vs E2E vs fixture."""

from __future__ import annotations

from app.config import settings

E2E_TEST_EMAIL = "e2e@test.local"


def database_name() -> str:
    url = (settings.database_url or "").lower()
    if "career_os_e2e" in url:
        return "career_os_e2e"
    if "career_os" in url:
        return "career_os"
    return "unknown"


def is_e2e_database() -> bool:
    return database_name() == "career_os_e2e"


def is_owner_database() -> bool:
    return not is_e2e_database()


def is_e2e_account(email: str | None) -> bool:
    return (email or "").strip().lower() == E2E_TEST_EMAIL


def deployment_badge() -> str:
    if settings.oauth_fixture_mode and settings.app_env in {"test", "local"} and is_e2e_database():
        return "E2E TEST"
    if settings.oauth_fixture_mode and not is_e2e_database():
        return "FIXTURE"
    if is_e2e_database() or settings.app_env == "test":
        return "E2E TEST"
    return "OWNER LOCAL"


def environment_payload() -> dict:
    badge = deployment_badge()
    return {
        "badge": badge,
        "app_env": settings.app_env,
        "database": database_name(),
        "db_identity_purpose": settings.aarohan_db_identity_purpose or None,
        "db_identity_uuid": settings.aarohan_db_identity_uuid or None,
        "runtime_profile": settings.aarohan_runtime_profile,
        "oauth_fixture_mode": settings.oauth_fixture_mode,
        "connector_fixture_mode": settings.connector_fixture_mode,
        "is_owner_stack": badge == "OWNER LOCAL",
        "is_e2e_stack": badge == "E2E TEST",
        "show_fixture_controls": badge in {"E2E TEST", "FIXTURE"},
        "e2e_login_allowed": settings.allow_e2e_login_on_owner or not is_owner_database(),
        "local_dev_auth_bypass": settings.local_dev_auth_bypass and settings.app_env == "local",
        "api_port_hint": 8001 if is_e2e_database() else 8000,
        "web_port_hint": 3001 if is_e2e_database() else 3000,
    }


def assert_e2e_user_allowed(email: str) -> None:
    if is_e2e_account(email) and is_owner_database() and not settings.allow_e2e_login_on_owner:
        raise PermissionError(
            "The E2E test account cannot sign in to the owner stack. "
            "Use the isolated E2E app at http://localhost:3001."
        )
