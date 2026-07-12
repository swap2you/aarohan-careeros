from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

FRESH_JOBS_MAX_AGE_HOURS = 168  # TODAY+FRESH+RECENT default visibility window


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        extra="ignore",
    )

    app_env: str = "development"
    app_secret: str = ""
    database_url: str = ""
    token_encryption_key: str = ""
    admin_email: str = ""
    admin_password: str = ""
    scheduling_enabled: bool = False
    enable_scheduled_workflows: bool = False
    enable_final_application_submission: bool = False
    enable_external_email_send: bool = False

    google_client_id: str = ""
    google_client_secret: str = ""
    google_drive_folder_id: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/integrations/google/callback"
    google_oauth_client_json_path: str = ""
    google_cloud_project_id: str = ""
    google_cloud_project_number: str = ""

    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    career_gmail_address: str = ""
    test_email_allowlist: str = ""

    ai_provider: str = "openrouter"
    ai_api_key: str = ""
    ai_monthly_soft_cap_usd: float = 75.0
    ai_monthly_hard_cap_usd: float = 150.0
    ai_per_job_packet_cap_usd: float = 3.0
    ai_per_interview_pack_cap_usd: float = 8.0

    config_root: str = "/app/config"
    career_vault_root: str = "/app/career_vault"
    generated_root: str = "/app/generated"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    oauth_fixture_mode: bool = False

    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    jooble_api_key: str = ""
    usajobs_api_key: str = ""
    usajobs_user_email: str = ""
    rss_feed_urls: str = ""
    connector_fixture_mode: bool = False
    lever_api_base: str = "https://api.lever.co/v0/postings"

    ask_aarohan_sql_mode: str = "read_only"
    ask_aarohan_allow_mutations: bool = False
    ask_aarohan_model: str = "gpt-4o-mini"
    openai_tts_model: str = "tts-1"
    allow_legacy_jwt_auth: bool = False
    expose_session_token_in_login_response: bool = False
    allow_e2e_login_on_owner: bool = False
    local_dev_auth_bypass: bool = False
    gmail_sync_start_date: str = ""
    deployment_mode: str = ""
    aarohan_runtime_profile: str = ""
    aarohan_db_identity_purpose: str = ""
    aarohan_db_identity_uuid: str = ""
    destructive_operation_token: str = ""
    migration_database_url: str = ""

    @model_validator(mode="after")
    def resolve_runtime_paths(self) -> "Settings":
        """Use repository-local paths when Docker /app mount paths are unavailable."""
        from pathlib import Path

        api_root = Path(__file__).resolve().parents[1]
        if (api_root / "config").exists():
            repo_root = api_root
        elif len(api_root.parents) > 1:
            repo_root = api_root.parents[1]
        else:
            repo_root = api_root

        def local_or_keep(value: str, relative: Path) -> str:
            path = Path(value)
            if path.is_absolute() and str(path).replace("\\", "/").startswith("/app"):
                if not path.parent.exists():
                    return str(relative)
            return value

        self.config_root = local_or_keep(self.config_root, repo_root / "config")
        self.career_vault_root = local_or_keep(self.career_vault_root, repo_root / "career_vault")
        self.generated_root = local_or_keep(self.generated_root, api_root / "generated")
        return self

    @model_validator(mode="after")
    def load_google_oauth_from_json(self) -> "Settings":
        if self.google_client_id and self.google_client_secret:
            return self
        json_path = self.google_oauth_client_json_path
        if not json_path:
            return self
        from pathlib import Path
        import json

        path = Path(json_path)
        if not path.exists():
            return self
        data = json.loads(path.read_text(encoding="utf-8"))
        web = data.get("web") or data.get("installed") or {}
        if not self.google_client_id:
            self.google_client_id = web.get("client_id", "")
        if not self.google_client_secret:
            self.google_client_secret = web.get("client_secret", "")
        redirect_uris = web.get("redirect_uris") or []
        if redirect_uris and self.google_oauth_redirect_uri == (
            "http://localhost:8000/api/integrations/google/callback"
        ):
            preferred = next(
                (uri for uri in redirect_uris if "localhost:8000" in uri),
                redirect_uris[0],
            )
            self.google_oauth_redirect_uri = preferred
        return self


settings = Settings()
