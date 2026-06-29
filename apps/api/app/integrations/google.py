from abc import ABC, abstractmethod


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
        return [
            {
                "id": "fixture-msg-1",
                "sender": "recruiter@example.com",
                "subject": "Interview availability for Director of QE",
                "body_text": "We would like to schedule an interview for the Director role.",
            }
        ]
