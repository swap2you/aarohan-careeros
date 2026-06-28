from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.google import FixtureGmailClient, FixtureGoogleDriveClient, GmailClient, GoogleDriveClient
from app.services.google_api import (
    ensure_drive_folder_tree,
    fetch_aarohan_labeled_messages,
    fetch_gmail_messages,
    upload_file_to_drive,
)
from app.services.oauth import get_token


class LiveGmailClient(GmailClient):
    def __init__(self, db: Session):
        self.db = db

    def fetch_recent_messages(self, query: str = "", max_results: int = 20) -> list[dict]:
        if not get_token(self.db, "gmail"):
            return []
        label_query = query or "label:Aarohan OR subject:(interview OR recruiter OR application OR rejection)"
        if not query:
            return fetch_aarohan_labeled_messages(self.db, max_results=max_results)
        return fetch_gmail_messages(self.db, query=label_query, max_results=max_results)


class LiveGoogleDriveClient(GoogleDriveClient):
    def __init__(self, db: Session):
        self.db = db
        self._folder_cache: dict[str, str] | None = None

    def _folders(self) -> dict[str, str]:
        if self._folder_cache is None:
            self._folder_cache = ensure_drive_folder_tree(self.db)
        return self._folder_cache

    def upload_file(self, local_path: str, filename: str, folder_id: str | None = None) -> str:
        target = folder_id
        if not target:
            folders = self._folders()
            target = folders.get("02_Application_Packets", settings.google_drive_folder_id)
        result = upload_file_to_drive(self.db, local_path, filename, folder_id=target)
        return result.get("web_view_link") or f"drive://{target}/{filename}"


def get_gmail_client(db: Session) -> GmailClient:
    if settings.oauth_fixture_mode:
        return FixtureGmailClient()
    return LiveGmailClient(db)


def get_drive_client(db: Session) -> GoogleDriveClient:
    if settings.oauth_fixture_mode:
        return FixtureGoogleDriveClient()
    return LiveGoogleDriveClient(db)


def sync_drive_folders(db: Session) -> dict[str, str]:
    if settings.oauth_fixture_mode:
        from app.services.google_api import DRIVE_SUBFOLDERS

        return {name: f"fixture-{name}" for name in DRIVE_SUBFOLDERS}
    from app.services.drive_settings import sync_drive_subfolders

    return sync_drive_subfolders(db)
