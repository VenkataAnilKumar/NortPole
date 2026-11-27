"""Fail-closed Google Drive eligibility and request-time access for one pilot library."""

import re
from collections.abc import Collection
from os import environ
from time import monotonic
from urllib.parse import urlsplit

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from nortpole.access.cc_pair_access import get_cc_pair_access_mode
from nortpole.configs.constants import DocumentSource
from nortpole.connectors.credentials_provider import build_db_credentials_provider
from nortpole.connectors.google_drive.source_operations import (
    GoogleDriveSourceOperations,
)
from nortpole.context.search.models import CCPairAccessMode
from nortpole.db.connector_credential_pair import build_user_acl_cc_pair_filter
from nortpole.db.document_set import get_document_set_by_id_for_user
from nortpole.db.enums import AccessType, ConnectorCredentialPairStatus
from nortpole.db.models import (
    Connector,
    ConnectorCredentialPair,
    Document,
    DocumentByConnectorCredentialPair,
    DocumentSet__ConnectorCredentialPair,
    User,
)
from nortpole.utils.logger import setup_logger
from shared_configs.contextvars import get_current_tenant_id

logger = setup_logger()
MAX_PILOT_CHECKS = 12
PILOT_CHECK_WINDOW_SECONDS = 8
_FILE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,200}$")


def eligible_drive_library(
    user: User, db: Session, *, library_names: Collection[str] | None = None,
) -> int | None:
    library = environ.get("NORTPOLE_SEARCH_DRIVE_PILOT_LIBRARY_ID", "")
    if not (
        len(library) <= 10
        and library.isascii()
        and library.isdecimal()
        and 0 < int(library) < 2**31
        and user.is_verified
        and user.email
        and get_current_tenant_id()
        == environ.get("NORTPOLE_SEARCH_DRIVE_PILOT_TENANT", "public")
        and get_cc_pair_access_mode(db) == CCPairAccessMode.ENFORCE
    ):
        return None
    library_id = int(library)
    document_set = get_document_set_by_id_for_user(db, library_id, user, get_editable=False)
    if document_set is None or (
        library_names is not None and document_set.name not in library_names
    ):
        return None
    pair = ConnectorCredentialPair
    linked = DocumentSet__ConnectorCredentialPair
    has_active_drive = db.scalar(
        select(
            select(pair.id)
            .join(linked, linked.connector_credential_pair_id == pair.id)
            .join(Connector, Connector.id == pair.connector_id)
            .where(
                linked.document_set_id == library_id,
                linked.is_current.is_(True),
                Connector.source == DocumentSource.GOOGLE_DRIVE,
                pair.status == ConnectorCredentialPairStatus.ACTIVE,
                pair.perm_sync_pending_since.is_(None),
                pair.access_type.in_(AccessType.perm_synced_types()),
                build_user_acl_cc_pair_filter(user.id),
            )
            .exists()
        )
    )
    return library_id if has_active_drive else None


def _file_id(document_id: str) -> str | None:
    try:
        parsed = urlsplit(document_id)
        if parsed.scheme != "https" or parsed.netloc not in {
            "drive.google.com",
            "docs.google.com",
        }:
            return None
        segments = parsed.path.strip("/").split("/")
        if "d" in segments:
            identifier = segments[segments.index("d") + 1]
            if _FILE_ID.fullmatch(identifier):
                return identifier
    except (ValueError, IndexError):
        pass
    return None


def live_drive_destinations(
    ids: Collection[str], user: User, db: Session, *, library_names: Collection[str] | None = None,
) -> dict[str, str | None]:
    """Authorize only verified, named readers, using fresh ACLs for each request."""
    if not ids or (
        library_id := eligible_drive_library(user, db, library_names=library_names)
    ) is None:
        return {}
    pair = ConnectorCredentialPair
    mapping = DocumentByConnectorCredentialPair
    linked = DocumentSet__ConnectorCredentialPair
    rows = db.execute(
        select(Document.id, pair.credential_id)
        .join(mapping, mapping.id == Document.id)
        .join(
            pair,
            and_(
                pair.connector_id == mapping.connector_id,
                pair.credential_id == mapping.credential_id,
            ),
        )
        .join(Connector, Connector.id == pair.connector_id)
        .join(linked, linked.connector_credential_pair_id == pair.id)
        .where(
            Document.id.in_(ids),
            Document.hidden.is_(False),
            mapping.has_been_indexed.is_(True),
            Connector.source == DocumentSource.GOOGLE_DRIVE,
            linked.document_set_id == library_id,
            linked.is_current.is_(True),
            pair.status == ConnectorCredentialPairStatus.ACTIVE,
            pair.perm_sync_pending_since.is_(None),
            pair.access_type.in_(AccessType.perm_synced_types()),
            build_user_acl_cc_pair_filter(user.id),
        )
        .order_by(pair.id)
    )
    credentials: dict[str, int] = {}
    for document_id, credential_id in rows:
        credentials.setdefault(document_id, credential_id)

    started = monotonic()
    destinations: dict[str, str | None] = {}
    clients: dict[int, GoogleDriveSourceOperations] = {}
    unusable: set[int] = set()
    checked = 0
    for document_id in ids:
        credential = credentials.get(document_id)
        file_id = _file_id(document_id)
        if not file_id or credential is None or credential in unusable:
            continue
        if (
            checked >= MAX_PILOT_CHECKS
            or monotonic() - started >= PILOT_CHECK_WINDOW_SECONDS
        ):
            break
        checked += 1
        if credential not in clients:
            clients[credential] = GoogleDriveSourceOperations(
                credentials_provider=build_db_credentials_provider(
                    DocumentSource.GOOGLE_DRIVE, credential
                )
            )
        try:
            if clients[credential].confirm_named_file_access(
                file_id=file_id,
                viewer_email=user.email.strip().casefold(),
            ):
                destinations[document_id] = (
                    f"https://drive.google.com/open?id={file_id}"
                )
        except Exception as error:
            logger.info(
                "Drive pilot permissions unavailable (%s)", type(error).__name__
            )
            # An authorization failure always withholds this file. Stop using the
            # credential if the source is unavailable or rate-limiting the request.
            if getattr(getattr(error, "response", None), "status_code", None) not in (
                403,
                404,
            ):
                unusable.add(credential)
    return destinations
