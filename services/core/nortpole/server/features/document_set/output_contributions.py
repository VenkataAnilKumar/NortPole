import hashlib
import re
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from nortpole.auth.permissions import has_permission, require_permission
from nortpole.configs.app_configs import DISABLE_VECTOR_DB
from nortpole.configs.constants import DocumentSource, FileOrigin
from nortpole.db.connector_credential_pair import (
    lock_connector_credential_pair_row,
    verify_user_can_edit_connector,
)
from nortpole.db.document_set import (
    fetch_all_document_sets_for_user,
    get_document_set_by_id_for_user,
)
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import AccessType, IndexingMode, Permission, PermissionAuthority
from nortpole.db.models import (
    Connector,
    ConnectorCredentialPair,
    DocumentSet,
    DocumentSet__ConnectorCredentialPair,
    User,
    UserGroup__CCPairDataAccess,
)
from nortpole.file_store.constants import CONTENT_SHA256_METADATA_KEY
from nortpole.file_store.file_store import get_default_file_store
from nortpole.server.documents.connector import (
    _normalize_file_names_for_backwards_compatibility,
)

router = APIRouter()


class Destination(BaseModel):
    id: int
    name: str
    is_public: bool
    audience_key: str


class Contribution(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    format: Literal["md", "csv"]
    text: str = Field(min_length=1, max_length=2_000_000)
    audience_key: str = Field(pattern=r"^[0-9a-f]{64}$")


def _audience_key(collection: DocumentSet, pair: ConnectorCredentialPair) -> str:
    groups = sorted(group.id for group in collection.groups)
    return hashlib.sha256(
        f"{collection.is_public}/{pair.id}/{groups}".encode()
    ).hexdigest()


def _has_write_permissions(user: User) -> bool:
    return all(
        has_permission(user, permission) is not PermissionAuthority.NONE
        for permission in (
            Permission.MANAGE_DOCUMENT_SETS,
            Permission.MANAGE_CONNECTORS,
        )
    )


def _destination_pair(
    db: Session, collection: DocumentSet, user: User, *, lock: bool = False
) -> ConnectorCredentialPair | None:
    # A file source may serve other collections or have its own wider ACL.
    # Publish only to a dedicated, active source with the collection's audience.
    if not collection.is_up_to_date:
        return None
    scope = {group.id for group in collection.groups}
    members = DocumentSet__ConnectorCredentialPair
    for candidate in sorted(
        collection.connector_credential_pairs, key=lambda pair: pair.id
    ):
        if candidate.connector.source != DocumentSource.FILE:
            continue
        if lock:
            # Match the connector editor's pair-before-connector lock order.
            pair = lock_connector_credential_pair_row(db, candidate.id)
            connector_id = db.scalar(
                select(Connector.id)
                .where(Connector.id == candidate.connector_id)
                .with_for_update()
            )
            if pair is None or connector_id is None:
                continue
        else:
            pair = candidate
        pair_ids = list(
            db.scalars(
                select(ConnectorCredentialPair.id).where(
                    ConnectorCredentialPair.connector_id == pair.connector_id
                )
            )
        )
        if pair_ids != [pair.id] or not pair.status.is_active():
            continue
        linked = set(
            db.scalars(
                select(members.document_set_id).where(
                    members.connector_credential_pair_id == pair.id
                )
            )
        )
        if linked != {collection.id} or not verify_user_can_edit_connector(
            pair.connector_id, db, user
        ):
            continue
        if collection.is_public and pair.access_type == AccessType.PUBLIC:
            return pair
        if (
            not collection.is_public
            and scope
            and pair.access_type == AccessType.PRIVATE
        ):
            access = set(
                db.scalars(
                    select(UserGroup__CCPairDataAccess.user_group_id).where(
                        UserGroup__CCPairDataAccess.cc_pair_id == pair.id
                    )
                )
            )
            if access == scope:
                return pair
    return None


@router.get("/document-set/output-destinations")
def destinations(
    user: User = Depends(require_permission(Permission.READ_SEARCH)),
    db: Session = Depends(get_session),
) -> list[Destination]:
    if DISABLE_VECTOR_DB or not _has_write_permissions(user):
        return []
    return [
        Destination(
            id=collection.id,
            name=collection.name,
            is_public=collection.is_public,
            audience_key=_audience_key(collection, pair),
        )
        for collection in fetch_all_document_sets_for_user(db, user, get_editable=True)
        if (pair := _destination_pair(db, collection, user)) is not None
    ]


@router.post("/document-set/{collection_id}/outputs")
def contribute_output(
    collection_id: int,
    body: Contribution,
    user: User = Depends(require_permission(Permission.READ_SEARCH)),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    if DISABLE_VECTOR_DB or not _has_write_permissions(user):
        raise HTTPException(403, "Collection contributions are unavailable")
    if (
        db.scalar(
            select(DocumentSet.id)
            .where(DocumentSet.id == collection_id)
            .with_for_update()
        )
        is None
    ):
        raise HTTPException(404, "Collection not found")
    collection = get_document_set_by_id_for_user(
        db, collection_id, user, get_editable=True
    )
    if collection is None:
        raise HTTPException(404, "Collection not found")
    pair = _destination_pair(db, collection, user, lock=True)
    if pair is None:
        raise HTTPException(409, "Collection has no eligible file source")
    if body.audience_key != _audience_key(collection, pair):
        raise HTTPException(409, "Collection audience has changed")

    content = body.text.encode("utf-8")
    if len(content) > 2_000_000 or not body.text.strip() or "\x00" in body.text:
        raise HTTPException(422, "Use non-empty UTF-8 text up to 2 MB")
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", body.name).strip(". ") or "Output"
    filename = f"{title}.{body.format}"
    digest = hashlib.sha256(content).hexdigest()
    key = hashlib.sha256(
        f"{pair.connector_id}/{filename}/{digest}".encode()
    ).hexdigest()
    file_id = f"collection-output-{key}"
    connector = db.get(Connector, pair.connector_id, populate_existing=True)
    assert connector is not None  # The connector and pair are locked above.
    config = connector.connector_specific_config
    locations = config.get("file_locations", [])
    if file_id not in locations:
        file_type = "text/csv" if body.format == "csv" else "text/markdown"
        store = get_default_file_store()
        if not store.has_file(file_id, FileOrigin.CONNECTOR, file_type):
            store.save_file(
                BytesIO(content),
                filename,
                FileOrigin.CONNECTOR,
                file_type,
                {CONTENT_SHA256_METADATA_KEY: digest},
                file_id,
            )
        names = _normalize_file_names_for_backwards_compatibility(
            locations, config.get("file_names", [])
        )
        connector.connector_specific_config = {
            **config,
            "file_locations": [*locations, file_id],
            "file_names": [*names, filename],
        }
        pair.indexing_trigger = pair.indexing_trigger or IndexingMode.UPDATE
        db.commit()
    return {"name": filename}
