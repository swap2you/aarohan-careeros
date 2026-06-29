from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "gmail" / "messages.json"


class GoogleDriveClient(ABC):
    @abstractmethod
    def upload_file(self, local_path: str, filename: str, folder_id: str | None = None) -> str:
        raise NotImplementedError


class StubGoogleDriveClient(GoogleDriveClient):
    def upload_file(self, local_path: str, filename: str, folder_id: str | None = None) -> str:
        return f"stub-drive://{folder_id or 'root'}/{filename}"


class FixtureGoogleDriveClient(GoogleDriveClient):
    _counter = 0

    def upload_file(self, local_path: str, filename: str, folder_id: str | None = None) -> str:
        FixtureGoogleDriveClient._counter += 1
        fid = f"fixture-file-{FixtureGoogleDriveClient._counter}"
        root = folder_id or "fixture-root"
        return f"https://drive.fixture.local/{root}/{fid}/{filename}"


class GmailClient(ABC):
    @abstractmethod
    def fetch_recent_messages(self, query: str = "", max_results: int = 20) -> list[dict]:
        raise NotImplementedError


class StubGmailClient(GmailClient):
    def fetch_recent_messages(self, query: str = "", max_results: int = 20) -> list[dict]:
        return []


class FixtureGmailClient(GmailClient):
    def fetch_recent_messages(self, query: str = "", max_results: int = 20) -> list[dict]:
        if not _FIXTURE_PATH.exists():
            return []
        data = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        return data[:max_results]
