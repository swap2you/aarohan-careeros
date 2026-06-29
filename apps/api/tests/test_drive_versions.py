"""Google Drive fixture version immutability tests."""

from app.integrations.google import FixtureGoogleDriveClient


def test_fixture_drive_client_unique_uris():
    FixtureGoogleDriveClient._counter = 0
    client = FixtureGoogleDriveClient()
    a = client.upload_file("/tmp/a.pdf", "a.pdf", "folder")
    b = client.upload_file("/tmp/b.pdf", "b.pdf", "folder")
    assert a != b
    assert "fixture-file-1" in a
    assert "fixture-file-2" in b


def test_fixture_drive_preserves_folder_in_uri():
    client = FixtureGoogleDriveClient()
    uri = client.upload_file("/tmp/resume.pdf", "resume.pdf", "packets-root")
    assert "packets-root" in uri
