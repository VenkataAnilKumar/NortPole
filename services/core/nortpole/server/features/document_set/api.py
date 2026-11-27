from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from nortpole.access.hierarchy_access import get_user_external_group_ids
from nortpole.auth.permission_projection import document_set_permissions
from nortpole.auth.permissions import (
    has_permission,
    require_permission,
)
from nortpole.auth.scoped_permissions import (
    assert_within_scope,
)
from nortpole.background.celery.versioned_apps.client import app as client_app
from nortpole.configs.app_configs import DISABLE_VECTOR_DB
from nortpole.configs.constants import NortPoleCeleryPriority, NortPoleCeleryTask
from nortpole.db.connector_credential_pair import (
    CCPairAccessLevel,
    get_connector_credential_pairs_for_user,
)
from nortpole.db.document_access import apply_document_access_filter
from nortpole.db.document_set import (
    check_document_sets_are_public,
    construct_document_id_select_by_docset,
    fetch_all_document_sets_for_user,
    get_document_set_by_id,
    get_document_set_by_id_for_user,
    get_group_ids_for_document_set,
    insert_document_set,
    mark_document_set_as_to_be_deleted,
    update_document_set,
    user_owns_groupless_document_set,
)
from nortpole.db.document_set import delete_document_set as db_delete_document_set
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission, PermissionAuthority
from nortpole.db.models import Document, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.features.document_set.models import (
    CheckDocSetPublicRequest,
    CheckDocSetPublicResponse,
    CollectionDocument,
    CollectionDocumentPage,
    DocumentSetCreationRequest,
    DocumentSetSummary,
    DocumentSetUpdateRequest,
)
from nortpole.server.features.document_set.output_contributions import router as contribution_router
from nortpole.server.features.document_set.policy_rules import router as policy_router
from nortpole.server.utils_vector_db import require_vector_db
from shared_configs.contextvars import get_current_tenant_id

router = APIRouter(prefix="/manage")
router.include_router(contribution_router)
router.include_router(policy_router)


@router.post("/admin/document-set")
def create_document_set(
    document_set_creation_request: DocumentSetCreationRequest,
    user: User = Depends(
        require_permission(Permission.MANAGE_DOCUMENT_SETS, allow_scope=True)
    ),
    db_session: Session = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
) -> int:
    # GATE 2 write authorization (see assert_within_scope).
    assert_within_scope(
        user,
        db_session,
        permission=Permission.MANAGE_DOCUMENT_SETS,
        current_group_ids=[],
        requested_group_ids=document_set_creation_request.groups or [],
        is_non_public=not document_set_creation_request.is_public,
    )
    try:
        document_set_db_model, _ = insert_document_set(
            document_set_creation_request=document_set_creation_request,
            user_id=user.id,
            db_session=db_session,
        )
    except Exception as e:
        raise NortPoleError(NortPoleErrorCode.VALIDATION_ERROR, str(e))

    if not DISABLE_VECTOR_DB:
        client_app.send_task(
            NortPoleCeleryTask.CHECK_FOR_VESPA_SYNC_TASK,
            kwargs={"tenant_id": tenant_id},
            priority=NortPoleCeleryPriority.HIGH,
        )

    return document_set_db_model.id


def _assert_attachable_cc_pairs(
    user: User, db_session: Session, cc_pair_ids: list[int]
) -> None:
    """Bounds attachments to the connectors the caller can already reach: public and
    sync pairs, pairs in a group they belong to, pairs they may operate, and groupless
    pairs they created. ``update_document_set`` checks connectors against the
    *requested* groups, so it checks nothing once those are empty; only the operate
    query carries the creator fallback."""
    if not cc_pair_ids:
        return

    attachable = {
        cc_pair.id
        for access_level in (CCPairAccessLevel.READ, CCPairAccessLevel.OPERATE)
        for cc_pair in get_connector_credential_pairs_for_user(
            db_session=db_session,
            user=user,
            access_level=access_level,
            ids=cc_pair_ids,
            processing_mode=None,
        )
    }
    if set(cc_pair_ids) - attachable:
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "Document set references a connector you do not have access to.",
        )


@router.patch("/admin/document-set")
def patch_document_set(
    document_set_update_request: DocumentSetUpdateRequest,
    user: User = Depends(
        require_permission(Permission.MANAGE_DOCUMENT_SETS, allow_scope=True)
    ),
    db_session: Session = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
) -> None:
    # Locked for the whole gate → write, so a concurrent admin edit is not reverted.
    document_set = get_document_set_by_id(
        db_session, document_set_update_request.id, for_update=True
    )
    if document_set is None:
        raise NortPoleError(
            NortPoleErrorCode.DOCUMENT_SET_NOT_FOUND,
            f"Document set {document_set_update_request.id} does not exist",
        )

    # GATE 2, and it must stay outside the try below, which would turn its 403 into a
    # 400. Groups and privacy come from the locked row, never the request, so a manager
    # can neither capture a set by reassigning it nor pull a public one private.
    if (
        has_permission(user, Permission.MANAGE_DOCUMENT_SETS)
        is not PermissionAuthority.GLOBAL
    ):
        current_group_ids = get_group_ids_for_document_set(db_session, document_set.id)
        stays_non_public = (
            not document_set.is_public and not document_set_update_request.is_public
        )
        # A set in no group has no scope to test, so only its creator may edit it in
        # place; adding a group puts it back under the scope gate.
        creator_editing_in_place = (
            document_set.user_id == user.id
            and not current_group_ids
            and not document_set_update_request.groups
            and stays_non_public
        )
        if not creator_editing_in_place:
            assert_within_scope(
                user,
                db_session,
                permission=Permission.MANAGE_DOCUMENT_SETS,
                current_group_ids=current_group_ids,
                requested_group_ids=document_set_update_request.groups,
                is_non_public=stays_non_public,
            )
        _assert_attachable_cc_pairs(
            user, db_session, document_set_update_request.cc_pair_ids
        )

    try:
        update_document_set(
            document_set_update_request=document_set_update_request,
            db_session=db_session,
            user=user,
        )
    except Exception as e:
        raise NortPoleError(NortPoleErrorCode.VALIDATION_ERROR, str(e))

    if not DISABLE_VECTOR_DB:
        client_app.send_task(
            NortPoleCeleryTask.CHECK_FOR_VESPA_SYNC_TASK,
            kwargs={"tenant_id": tenant_id},
            priority=NortPoleCeleryPriority.HIGH,
        )


@router.delete("/admin/document-set/{document_set_id}")
def delete_document_set(
    document_set_id: int,
    user: User = Depends(
        require_permission(Permission.MANAGE_DOCUMENT_SETS, allow_scope=True)
    ),
    db_session: Session = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
) -> None:
    # Serialize the delete marker with document-set and group-share updates.
    document_set = get_document_set_by_id(db_session, document_set_id, for_update=True)
    if document_set is None:
        raise NortPoleError(
            NortPoleErrorCode.DOCUMENT_SET_NOT_FOUND,
            f"Document set {document_set_id} does not exist",
        )

    # GATE 2: delete is admin-only (it triggers index cleanup), except a groupless set
    # its creator made — that one is shared with nobody
    is_admin = (
        has_permission(user, Permission.MANAGE_DOCUMENT_SETS)
        is PermissionAuthority.GLOBAL
    )
    if not is_admin and not user_owns_groupless_document_set(document_set, user):
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "Deleting a shared document set is restricted to administrators.",
        )

    try:
        mark_document_set_as_to_be_deleted(
            db_session=db_session,
            document_set_id=document_set_id,
            user=user,
        )
    except Exception as e:
        raise NortPoleError(NortPoleErrorCode.VALIDATION_ERROR, str(e))

    if DISABLE_VECTOR_DB:
        db_session.refresh(document_set)
        db_delete_document_set(document_set, db_session)
    else:
        client_app.send_task(
            NortPoleCeleryTask.CHECK_FOR_VESPA_SYNC_TASK,
            kwargs={"tenant_id": tenant_id},
            priority=NortPoleCeleryPriority.HIGH,
        )


@router.get("/admin/document-set/{document_set_id}")
def get_document_set(
    document_set_id: int,
    user: User = Depends(
        require_permission(Permission.MANAGE_DOCUMENT_SETS, allow_scope=True)
    ),
    db_session: Session = Depends(get_session),
) -> DocumentSetSummary:
    """Read one document set.

    The listing is scoped to the caller, so a client managing a single set had
    to fetch every set and filter. This returns the same shape as the listing.
    """
    # The two scopes are not nested: the readable filter needs membership or a
    # public set, while the editable one matches a managed scope and a creator's
    # groupless set. The listing unions them, so this does too.
    readable = get_document_set_by_id_for_user(
        db_session=db_session,
        document_set_id=document_set_id,
        user=user,
        get_editable=False,
    )
    editable = get_document_set_by_id_for_user(
        db_session=db_session,
        document_set_id=document_set_id,
        user=user,
        get_editable=True,
    )
    document_set = readable or editable
    if document_set is None:
        raise NortPoleError(
            NortPoleErrorCode.DOCUMENT_SET_NOT_FOUND,
            f"Document set {document_set_id} does not exist",
        )

    is_document_sets_admin = (
        has_permission(user, Permission.MANAGE_DOCUMENT_SETS)
        is PermissionAuthority.GLOBAL
    )
    is_editable = is_document_sets_admin or editable is not None
    return DocumentSetSummary.from_model(
        document_set,
        permissions=document_set_permissions(
            is_editable=is_editable,
            is_document_sets_admin=is_document_sets_admin,
            owns_groupless=is_editable
            and user_owns_groupless_document_set(document_set, user),
        ),
    )


"""Endpoints for non-admins"""


@router.get("/document-set")
def list_document_sets_for_user(
    # Search filter vocabulary. READ_DOCUMENT_SETS is deliberately not used: it
    # means "see every document set", which this route must not grant — the
    # results stay ACL-filtered below.
    user: User = Depends(require_permission(Permission.READ_SEARCH)),
    db_session: Session = Depends(get_session),
    get_editable: bool = Query(
        False, description="If true, return editable document sets"
    ),
) -> list[DocumentSetSummary]:
    readable = fetch_all_document_sets_for_user(
        db_session=db_session, user=user, get_editable=get_editable
    )
    authority = has_permission(user, Permission.MANAGE_DOCUMENT_SETS)
    is_document_sets_admin = authority is PermissionAuthority.GLOBAL

    # Union the two result sets and stamp from membership, like the connector listing.
    # The editable query is the only one that surfaces a creator's groupless set, and
    # recomputing editability with within_scope instead would drift from the filter.
    if authority is PermissionAuthority.NONE:
        editable = []  # GATE 1 refuses their PATCH regardless
    elif get_editable or is_document_sets_admin:
        editable = list(readable)
    else:
        editable = list(
            fetch_all_document_sets_for_user(
                db_session=db_session, user=user, get_editable=True
            )
        )
    editable_ids = {ds.id for ds in editable}
    by_id = {ds.id: ds for ds in readable}
    by_id.update({ds.id: ds for ds in editable})
    document_sets = list(by_id.values())

    summaries: list[DocumentSetSummary] = []
    for ds in document_sets:
        is_editable = ds.id in editable_ids
        summaries.append(
            DocumentSetSummary.from_model(
                ds,
                permissions=document_set_permissions(
                    is_editable=is_editable,
                    is_document_sets_admin=is_document_sets_admin,
                    owns_groupless=is_editable
                    and user_owns_groupless_document_set(ds, user),
                ),
            )
        )
    return summaries


@router.get(
    "/document-set/{document_set_id}/documents",
    dependencies=[Depends(require_vector_db)],
)
def list_collection_documents(
    document_set_id: int,
    cursor: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    user: User = Depends(require_permission(Permission.READ_SEARCH)),
    db_session: Session = Depends(get_session),
) -> CollectionDocumentPage:
    if get_document_set_by_id_for_user(
        db_session, document_set_id, user, get_editable=False
    ) is None:
        raise NortPoleError(NortPoleErrorCode.DOCUMENT_SET_NOT_FOUND)

    member_ids = construct_document_id_select_by_docset(document_set_id).order_by(None)
    stmt = select(
        Document.id, Document.semantic_id, Document.link, Document.doc_updated_at
    ).where(Document.id.in_(member_ids), Document.hidden.is_(False))
    stmt = apply_document_access_filter(
        db_session,
        stmt,
        user.email,
        get_user_external_group_ids(db_session, user),
        user_id=user.id,
    )
    if cursor is not None:
        stmt = stmt.where(Document.id > cursor)

    rows = db_session.execute(
        stmt.distinct().order_by(Document.id).limit(limit + 1)
    ).all()
    return CollectionDocumentPage(
        documents=[
            CollectionDocument(id=doc_id, title=title, link=link, updated_at=updated_at)
            for doc_id, title, link, updated_at in rows[:limit]
        ],
        next_cursor=rows[limit - 1][0] if len(rows) > limit else None,
    )


@router.get("/document-set-public")
def document_set_public(
    check_public_request: CheckDocSetPublicRequest,
    _: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> CheckDocSetPublicResponse:
    is_public = check_document_sets_are_public(
        document_set_ids=check_public_request.document_set_ids, db_session=db_session
    )
    return CheckDocSetPublicResponse(is_public=is_public)
