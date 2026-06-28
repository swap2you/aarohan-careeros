from unittest.mock import MagicMock, patch

from app.services.google_api import (
    DEFAULT_GMAIL_LABELS,
    DRIVE_SUBFOLDERS,
    _decode_gmail_body,
    fetch_aarohan_labeled_messages,
    list_gmail_labels,
    resolve_aarohan_label_ids,
)


def test_gmail_label_names_defined():
    assert "Aarohan/Job Alerts" in DEFAULT_GMAIL_LABELS
    assert len(DEFAULT_GMAIL_LABELS) == 5


def test_resolve_aarohan_label_ids():
    token = {"access_token": "t"}
    labels = {name: f"id-{i}" for i, name in enumerate(DEFAULT_GMAIL_LABELS)}
    with patch("app.services.google_api.list_gmail_labels", return_value=labels):
        resolved = resolve_aarohan_label_ids(token)
    assert len(resolved) == 5
    assert resolved["Aarohan/Recruiters"] == "id-1"


def test_decode_multipart_html():
    import base64

    html = base64.urlsafe_b64encode(b"<p>Hello</p><script>x</script>").decode()
    payload = {
        "parts": [
            {"mimeType": "text/html", "body": {"data": html}},
        ]
    }
    text = _decode_gmail_body(payload)
    assert "Hello" in text
    assert "script" not in text.lower()


def test_drive_subfolders_count():
    assert len(DRIVE_SUBFOLDERS) == 6


def test_fetch_aarohan_fixture_mode():
    from unittest.mock import patch

    from app.services.google_api import fetch_aarohan_labeled_messages

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with patch("app.services.google_api.get_token", return_value={"fixture": True}):
        with patch("app.services.google_api.settings") as mock_settings:
            mock_settings.oauth_fixture_mode = True
            with patch("app.integrations.google.FixtureGmailClient") as mock_client:
                mock_client.return_value.fetch_recent_messages.return_value = []
                msgs = fetch_aarohan_labeled_messages(db, max_results=5)
    assert msgs == []
