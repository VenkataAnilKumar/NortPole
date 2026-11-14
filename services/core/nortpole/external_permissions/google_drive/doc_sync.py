"""Who may read a Google Drive file or folder, from Drive's own sharing. NortPole's implementation of the hook the
Drive connector calls when a source uses "sync" access (the upstream one is in the Enterprise package, which NortPole
does not ship). Written from Drive's documented permission model, not copied.

Mapping, failing closed where the meaning is unclear:

- ``user``: that address may read it (owners, editors, commenters and readers alike).
- ``group``: recorded, but grants nothing until NortPole syncs that group's members (nobody's access list holds an
  external group yet).
- ``domain`` ("anyone at example.com"): grants nothing for now; it needs a per-domain entry on both the document and
  the person, which is not built.
- ``anyone`` ("anyone with the link", or public on the web): never makes the file public here. Only the people and
  groups named on the file can find it in NortPole (the recommended default, 2026-11-14; the owner may change it).
- A removed (``deleted``) permission grants nothing.
- If the permissions cannot be read at all, only the person whose access found the file is granted (as upstream).
"""

from __future__ import annotations

from typing import Any

from nortpole.access.models import ExternalAccess
from nortpole.access.utils import build_ext_group_name_for_evolvxsi
from nortpole.configs.constants import DocumentSource
from nortpole.connectors.google_drive.file_retrieval import PERMISSION_FULL_DESCRIPTION
from nortpole.connectors.google_drive.source_operations import GoogleDriveSourceOperations
from nortpole.utils.logger import setup_logger

logger = setup_logger()

PERMISSION_LIST_FIELDS = f"nextPageToken, {PERMISSION_FULL_DESCRIPTION}"


def access_from_permissions(permissions: list[dict[str, Any]], add_prefix: bool = False) -> ExternalAccess:
    """The access list one set of Drive permissions grants, per the rules above."""
    emails: set[str] = set()
    groups: set[str] = set()
    for p in permissions:
        if p.get("deleted"):
            continue
        kind = p.get("type")
        email = (p.get("emailAddress") or "").strip().lower()
        if kind == "user" and email:
            emails.add(email)
        elif kind == "group" and email:
            groups.add(build_ext_group_name_for_evolvxsi(email, DocumentSource.GOOGLE_DRIVE) if add_prefix else email)
        # "domain" and "anyone" grant nothing (see the module notes).
    return ExternalAccess(external_user_emails=emails, external_user_group_ids=groups, is_public=False)


def _read_permissions(item: dict[str, Any], ops: GoogleDriveSourceOperations, readers: list[str]) -> list[dict[str, Any]] | None:
    """Permissions listed with the item, or fetched as the first reader who can. None when nobody can read them."""
    inline = item.get("permissions")
    if isinstance(inline, list) and (inline or not item.get("permissionIds")):
        return inline
    file_id = item.get("id")
    if not file_id:
        return None
    for reader in readers:
        try:
            return list(ops.list_file_permissions(user_email=reader, file_id=file_id, fields=PERMISSION_LIST_FIELDS))
        except Exception as e:  # noqa: BLE001 - try the next reader; an unreadable file falls back below
            logger.debug("Could not read Drive permissions for %s as %s: %s", file_id, reader, e)
    return None


def get_external_access_for_raw_gdrive_file(
    file: dict[str, Any],
    company_domain: str,  # noqa: ARG001 - domain sharing grants nothing yet (module notes)
    ops: GoogleDriveSourceOperations,
    retriever_email: str | None,
    admin_email: str,
    fallback_user_email: str,
    add_prefix: bool = False,
    fallback_retriever_email: str | None = None,
) -> ExternalAccess:
    readers = [r for r in (retriever_email, fallback_retriever_email, admin_email) if r]
    permissions = _read_permissions(file, ops, list(dict.fromkeys(readers)))
    if permissions is None:
        logger.info("Drive permissions unreadable for %s; granting only %s", file.get("id"), fallback_user_email)
        return ExternalAccess(external_user_emails={fallback_user_email.lower()}, external_user_group_ids=set(), is_public=False)
    return access_from_permissions(permissions, add_prefix)


def get_external_access_for_folder(
    folder: dict[str, Any],
    google_domain: str,  # noqa: ARG001 - as above
    ops: GoogleDriveSourceOperations,
    user_email: str,
    add_prefix: bool = False,
) -> ExternalAccess:
    """A folder's access, for browsing the folder tree. Unreadable permissions grant nothing."""
    permissions = _read_permissions(folder, ops, [user_email])
    if permissions is None:
        return ExternalAccess.empty()
    return access_from_permissions(permissions, add_prefix)
