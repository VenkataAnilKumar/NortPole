"""Read a scheduled review's CSV using the owner's Google Drive connection."""

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any
from uuid import UUID

import requests
from sqlalchemy.orm import Session
from urllib3.exceptions import HTTPError

from nortpole.chat.selected_sources import MAX_INLINE_CSV_BYTES
from nortpole.db.action_policy import get_gated_app_id, resolve_action_policies
from nortpole.db.enums import ActionPolicy, ExternalAppType, GatedAppKind
from nortpole.db.external_app import get_external_app_by_id, get_external_app_user_credential
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.external_apps.providers.google_drive import GoogleDriveAction
from nortpole.external_apps.token_refresh import ensure_fresh_credentials
from nortpole.work.workflow_schedules.models import DriveCsvSource
from shared_configs.contextvars import get_current_tenant_id

FILES_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
FOLDER_MIME = "application/vnd.google-apps.folder"
CSV_FIELDS = "id,name,version,size"
REQUEST_TIMEOUT = (5, 15)
MAX_LIST_PAGES = 10


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    version: str
    size: int


class NoNewDriveCsv(Exception):
    """An expected empty or unchanged folder."""


def drive_headers(db: Session, owner_id: UUID, app_id: int) -> dict[str, str]:
    app = get_external_app_by_id(db, app_id)
    credential = get_external_app_user_credential(db, external_app_id=app_id, user_id=owner_id)
    token = credential.user_credentials.get_value(apply_mask=False).get("access_token") if credential else None
    if app is None or not app.enabled or app.app_type != ExternalAppType.GOOGLE_DRIVE or not token:
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "Connect Google Drive in Sources before using this schedule.",
        )
    action = GoogleDriveAction.FILES_READ
    policies = resolve_action_policies(
        db, user_id=owner_id,
        gated_app_id=get_gated_app_id(db, GatedAppKind.EXTERNAL_APP, app_id),
        catalog_policies={action: ActionPolicy.ALWAYS},
    )
    if policies[action] != ActionPolicy.ALWAYS:
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "Google Drive's Read files action must be set to Always allow for scheduled reviews.",
        )
    return {"Authorization": f"Bearer {token}"}


def _get(url: str, headers: dict[str, str], params: dict[str, str]) -> requests.Response:
    try:
        response = requests.get(
            url, headers=headers, params=params, timeout=REQUEST_TIMEOUT, stream=True,
            allow_redirects=False,
        )
        if response.ok and response.status_code == 200:
            return response
        status = response.status_code
        response.close()
    except requests.RequestException as exc:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Google Drive could not be reached. Try again later.") from exc
    if status in (401, 403, 404):
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "The Google Drive connection cannot access the selected folder or file.",
        )
    raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Google Drive could not return the file. Try again later.")


def _metadata(url: str, headers: dict[str, str], params: dict[str, str]) -> dict[str, Any]:
    try:
        with _get(url, headers, params) as response:
            metadata = response.json()
            if not isinstance(metadata, dict):
                raise ValueError("Expected a Google Drive metadata object")
            return metadata
    except (requests.RequestException, ValueError) as exc:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Google Drive returned an unreadable response.") from exc


def folder_metadata(source: DriveCsvSource, headers: dict[str, str]) -> dict[str, Any]:
    folder = _metadata(
        f"{FILES_URL}/{source.folder_id}", headers,
        {"fields": "mimeType,trashed,driveId", "supportsAllDrives": "true"},
    )
    if folder.get("mimeType") != FOLDER_MIME or folder.get("trashed"):
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose an available Google Drive folder.")
    return folder


def validate_drive_source(db: Session, owner_id: UUID, source: DriveCsvSource) -> None:
    ensure_fresh_credentials(get_current_tenant_id(), source.app_id, owner_id)
    headers = drive_headers(db, owner_id, source.app_id)
    try:
        newest_csv(source, headers)
    except NoNewDriveCsv:
        # A folder can receive its first CSV after the schedule is saved.
        pass


def newest_csv(source: DriveCsvSource, headers: dict[str, str]) -> DriveFile:
    folder = folder_metadata(source, headers)
    params = {
        "q": f"'{source.folder_id}' in parents and trashed = false",
        "fields": f"nextPageToken,incompleteSearch,files({CSV_FIELDS},mimeType)",
        "orderBy": "modifiedTime desc,name",
        "pageSize": "100",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    if folder.get("driveId"):
        params.update(corpora="drive", driveId=folder["driveId"])
    for _ in range(MAX_LIST_PAGES):
        page = _metadata(FILES_URL, headers, params)
        if page.get("incompleteSearch"):
            raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Google Drive did not return a complete folder listing.")
        for file in page.get("files", []):
            name = file.get("name", "")
            if (
                name.lower().endswith(".csv")
                and fnmatchcase(name.casefold(), source.filename_pattern.strip().casefold())
                and not file.get("mimeType", "").startswith("application/vnd.google-apps.")
            ):
                if not DRIVE_ID.fullmatch(file.get("id", "")) or not file.get("version") or not str(file.get("size", "")).isdigit():
                    raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Google Drive did not return usable CSV metadata.")
                return DriveFile(file["id"], name, str(file["version"]), int(file["size"]))
        token = page.get("nextPageToken")
        if not token:
            raise NoNewDriveCsv("No CSV in the Google Drive folder matches the filename pattern.")
        params["pageToken"] = token
    raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "The Google Drive folder has too many files to search. Choose a smaller folder.")


def download_csv(file: DriveFile, headers: dict[str, str]) -> bytes:
    if not 0 < file.size <= MAX_INLINE_CSV_BYTES:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "The latest Google Drive CSV must contain data and be at most 12 KB.")
    url = f"{FILES_URL}/{file.id}"
    try:
        with _get(url, headers, {"alt": "media", "supportsAllDrives": "true"}) as response:
            content = response.raw.read(MAX_INLINE_CSV_BYTES + 1, decode_content=True)
    except (requests.RequestException, HTTPError, OSError) as exc:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Google Drive could not download the CSV. Try again later.") from exc

    after = _metadata(url, headers, {"fields": "version,trashed", "supportsAllDrives": "true"})
    if after.get("trashed") or str(after.get("version")) != file.version or len(content) != file.size:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "The Google Drive CSV changed during download. Try again at the next run.")
    try:
        if not content.decode("utf-8-sig").strip():
            raise ValueError("Empty CSV")
    except ValueError as exc:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "The Google Drive CSV must contain UTF-8 text.") from exc
    return content
