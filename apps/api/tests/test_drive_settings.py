from unittest.mock import MagicMock, patch

from app.services.drive_settings import (
    DRIVE_ROOT_INACCESSIBLE_WARNING,
    create_app_drive_root,
    is_drive_folder_accessible,
    resolve_active_drive_root,
    try_sync_drive_after_oauth,
)


def test_is_drive_folder_accessible_ok():
    token = {"access_token": "t"}
    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value.status_code = 200
        mock_client.return_value.__enter__.return_value.get.return_value.json.return_value = {
            "id": "abc",
            "trashed": False,
        }
        assert is_drive_folder_accessible(token, "abc") is True


def test_is_drive_folder_accessible_forbidden():
    token = {"access_token": "t"}
    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value.status_code = 404
        assert is_drive_folder_accessible(token, "abc") is False


def test_try_sync_drive_after_oauth_inaccessible_configured_root():
    db = MagicMock()
    with patch("app.services.drive_settings.get_token", return_value={"access_token": "t"}):
        with patch("app.services.drive_settings.resolve_active_drive_root", return_value=("cfg-id", "configured", False)):
            with patch("app.services.drive_settings.get_drive_root_status", return_value={"accessible": False}):
                result = try_sync_drive_after_oauth(db)
    assert result["ok"] is True
    assert DRIVE_ROOT_INACCESSIBLE_WARNING in result["warning"]


def test_create_app_drive_root_fixture():
    db = MagicMock()
    with patch("app.services.drive_settings.get_token", return_value={"fixture": True}):
        with patch("app.services.drive_settings.set_active_drive_root") as mock_set:
            with patch("app.services.drive_settings._set_setting"):
                result = create_app_drive_root(db)
    assert result["source"] == "app-created"
    assert "root_folder_id" in result
    mock_set.assert_called_once()


def test_resolve_active_drive_root_uses_stored_when_accessible():
    db = MagicMock()
    row = MagicMock()
    row.value = "stored-id"
    db.query.return_value.filter.return_value.one_or_none.side_effect = [row, MagicMock(value="app-created")]
    with patch("app.services.drive_settings.get_token", return_value={"access_token": "t"}):
        with patch("app.services.drive_settings.is_drive_folder_accessible", return_value=True):
            root_id, source, accessible = resolve_active_drive_root(db)
    assert root_id == "stored-id"
    assert accessible is True
