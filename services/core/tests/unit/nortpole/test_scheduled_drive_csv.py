from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from nortpole.db.enums import ActionPolicy, ExternalAppType
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.work.workflow_schedules import drive_csv, expense_review
from nortpole.work.workflow_schedules.models import DriveCsvSource, ExpenseReviewInputs


def test_exactly_one_csv_source():
    source = DriveCsvSource(app_id=1, folder_id="folder")
    assert ExpenseReviewInputs(library_id=1, drive_source=source).csv_file_id is None
    with pytest.raises(ValidationError, match="Choose one CSV source"):
        ExpenseReviewInputs(library_id=1, drive_source=source, csv_file_id=uuid4())
    with pytest.raises(ValidationError, match="Choose one CSV source"):
        ExpenseReviewInputs(library_id=1)


@pytest.mark.parametrize("policy", [ActionPolicy.ASK, ActionPolicy.DENY])
def test_requires_owners_connection_and_automatic_read_permission(monkeypatch, policy):
    owner = uuid4()
    app = SimpleNamespace(enabled=True, app_type=ExternalAppType.GOOGLE_DRIVE)
    monkeypatch.setattr(drive_csv, "get_external_app_by_id", Mock(return_value=app))
    credential = Mock()
    credential.user_credentials.get_value.return_value = {"access_token": "fixture"}
    owner_credential = Mock(return_value=credential)
    monkeypatch.setattr(drive_csv, "get_external_app_user_credential", owner_credential)
    monkeypatch.setattr(drive_csv, "get_gated_app_id", Mock(return_value=9))
    monkeypatch.setattr(drive_csv, "resolve_action_policies", Mock(
        return_value={drive_csv.GoogleDriveAction.FILES_READ: policy},
    ))
    db = Mock()
    with pytest.raises(NortPoleError, match="Always allow"):
        drive_csv.drive_headers(db, owner, 1)
    owner_credential.assert_called_once_with(db, external_app_id=1, user_id=owner)


def test_selects_first_matching_csv_across_drive_pages(monkeypatch):
    responses = iter([
        {"mimeType": drive_csv.FOLDER_MIME, "driveId": "shared"},
        {"files": [{"name": "other.csv"}], "nextPageToken": "page-two"},
        {"files": [
            {"name": "expenses-sheet.csv", "mimeType": "application/vnd.google-apps.spreadsheet"},
            {"id": "new", "name": "Expenses-Nov.CSV", "version": "12", "size": "47"},
            {"id": "old", "name": "expenses-oct.csv", "version": "8", "size": "43"},
        ]},
    ])
    calls = []

    def metadata(url, headers, params):
        calls.append(params.copy())
        return next(responses)

    monkeypatch.setattr(drive_csv, "_metadata", metadata)
    source = DriveCsvSource(app_id=1, folder_id="folder", filename_pattern="expenses-*.csv")
    assert drive_csv.newest_csv(source, {}) == drive_csv.DriveFile("new", "Expenses-Nov.CSV", "12", 47)
    assert calls[1]["orderBy"] == "modifiedTime desc,name"
    assert calls[2]["pageToken"] == "page-two"
    assert calls[2]["driveId"] == "shared"


def test_rejects_a_file_changed_during_download(monkeypatch):
    content = b"expense,receipt\nHotel,no\n"
    stream = Mock()
    stream.raw.read.return_value = content
    response = Mock()
    response.__enter__ = Mock(return_value=stream)
    response.__exit__ = Mock()
    monkeypatch.setattr(drive_csv, "_get", Mock(return_value=response))
    monkeypatch.setattr(drive_csv, "_metadata", Mock(return_value={"version": "2"}))
    with pytest.raises(NortPoleError, match="changed during download"):
        drive_csv.download_csv(drive_csv.DriveFile("file", "expenses.csv", "1", len(content)), {})
    stream.raw.read.assert_called_once_with(drive_csv.MAX_INLINE_CSV_BYTES + 1, decode_content=True)


def test_processed_revision_is_skipped_before_download(monkeypatch):
    monkeypatch.setattr(expense_review, "_resolve_library", Mock(return_value="Travel"))
    monkeypatch.setattr(expense_review, "is_craft_enabled_for_user", Mock(return_value=True))
    monkeypatch.setattr(expense_review, "ensure_fresh_credentials", Mock())
    monkeypatch.setattr(expense_review, "drive_headers", Mock(return_value={}))
    monkeypatch.setattr(expense_review, "newest_csv", Mock(
        return_value=drive_csv.DriveFile("file", "expenses.csv", "1", 46),
    ))
    download = Mock()
    monkeypatch.setattr(expense_review, "download_csv", download)
    db = Mock()
    db.scalar.return_value = uuid4()
    source = DriveCsvSource(app_id=1, folder_id="folder")
    with pytest.raises(drive_csv.NoNewDriveCsv, match="already been reviewed"):
        expense_review.run_drive_expense_review(
            db, SimpleNamespace(id=uuid4()), ExpenseReviewInputs(library_id=1, drive_source=source), uuid4(),
        )
    download.assert_not_called()
