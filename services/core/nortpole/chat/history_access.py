"""Reauthorize retained source inputs before replaying a chat branch."""

from collections.abc import Iterable

from sqlalchemy.orm import Session

from nortpole.access.access import censor_chunks_for_user
from nortpole.configs.constants import DocumentSource
from nortpole.context.search.models import (
    IndexFilters,
    PersonaSearchInfo,
    SearchDoc,
    TimeRange,
)
from nortpole.context.search.preprocessing.access_filters import (
    build_access_filters_for_user,
)
from nortpole.db.document_set import (
    fetch_document_sets_for_documents,
    filter_document_set_names_by_user_access,
)
from nortpole.db.models import SearchDoc as StoredSearchDoc
from nortpole.db.models import User
from nortpole.db.search_settings import get_current_search_settings
from nortpole.document_index.factory import get_default_document_index
from nortpole.document_index.interfaces import DocumentSectionRequest
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.features.search.drive_pilot import live_drive_destinations
from nortpole.server.features.search.workspace import (
    WORKSPACE_SOURCES,
    authorized_workspace_destinations,
)

EvidenceKey = tuple[str, int, DocumentSource]


def prior_sources_unavailable() -> NortPoleError:
    return NortPoleError(
        NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
        "Earlier evidence changed or is unavailable. Start a new chat to continue.",
    )


def workspace_evidence_keys(
    documents: Iterable[SearchDoc | StoredSearchDoc],
) -> set[EvidenceKey]:
    return {
        (doc.document_id, doc.chunk_ind, doc.source_type)
        for doc in documents
        if not doc.is_internet and doc.source_type != DocumentSource.WEB
    }


def verify_indexed_history(
    keys: set[EvidenceKey],
    persona: PersonaSearchInfo,
    user: User,
    db: Session,
    *,
    selected_libraries: tuple[str, ...] = (),
    recheck_drive: bool = False,
) -> None:
    if not keys:
        return
    scope = None
    if persona.document_set_names:
        scope = filter_document_set_names_by_user_access(
            db, persona.document_set_names, user
        )
    attached_ids = set(persona.attached_document_ids) if not selected_libraries else set()
    hierarchy_ids = persona.hierarchy_node_ids if not selected_libraries else []
    if selected_libraries:
        permitted = filter_document_set_names_by_user_access(
            db, list(selected_libraries), user
        )
        scope = (
            sorted(set(permitted).intersection(scope)) if scope is not None else permitted
        )
        if not scope:
            raise prior_sources_unavailable()
    needs_scope = bool(
        persona.document_set_names or selected_libraries or attached_ids or hierarchy_ids
    )
    folder_keys = (
        {key for key in keys if key[0] not in attached_ids} if needs_scope else set()
    )
    if scope and folder_keys:
        document_ids = sorted({doc_id for doc_id, _, _ in folder_keys})
        membership = dict(fetch_document_sets_for_documents(document_ids, db))
        accessible_libraries = set(scope)
        folder_keys = {
            key
            for key in folder_keys
            if accessible_libraries.isdisjoint(membership.get(key[0], ()))
        }
    if folder_keys and not hierarchy_ids:
        raise prior_sources_unavailable()
    access = build_access_filters_for_user(user, db)
    try:
        index = get_default_document_index(get_current_search_settings(db), None)
        filters = IndexFilters(
            access_control_list=access.access_control_list,
            cc_pair_access=access.cc_pair_access,
            updated_at_range=TimeRange(start=persona.search_start_date)
            if persona.search_start_date
            else None,
        )
        chunks = []
        # Live library membership and explicit attachment can qualify a document.
        # Other documents must still pass the folder scope in the index.
        for lookup_keys, lookup_filters in (
            (keys - folder_keys, filters),
            (folder_keys, filters.model_copy(update={"hierarchy_node_ids": hierarchy_ids})),
        ):
            if lookup_keys:
                doc_chunks = sorted({(doc, chunk) for doc, chunk, _ in lookup_keys})
                chunks.extend(index.id_based_retrieval(
                    [
                        DocumentSectionRequest(
                            document_id=doc, min_chunk_ind=chunk, max_chunk_ind=chunk
                        )
                        for doc, chunk in doc_chunks
                    ],
                    lookup_filters,
                ))
        chunks = censor_chunks_for_user(chunks, user)
    except NortPoleError:
        raise
    except Exception as error:
        raise NortPoleError(
            NortPoleErrorCode.SERVICE_UNAVAILABLE,
            "Earlier evidence could not be checked. Try again.",
        ) from error
    current = {
        (chunk.document_id, chunk.chunk_id, chunk.source_type)
        for chunk in chunks
        if not chunk.hidden
    }
    if not keys.issubset(current):
        raise prior_sources_unavailable()
    # The search index can temporarily retain a workspace grant after revocation.
    workspace = {
        chunk.document_id: chunk
        for chunk in chunks
        if chunk.source_type in (*WORKSPACE_SOURCES, DocumentSource.USER_FILE)
        and (chunk.document_id, chunk.chunk_id, chunk.source_type) in keys
    }
    if workspace:
        destinations = authorized_workspace_destinations(workspace, user, db)
        if workspace.keys() - destinations.keys():
            raise prior_sources_unavailable()
    if recheck_drive:
        drive_ids = sorted({
            doc_id for doc_id, _, source in keys if source == DocumentSource.GOOGLE_DRIVE
        })
        if drive_ids and set(drive_ids).difference(
            live_drive_destinations(drive_ids, user, db, library_names=scope or ())
        ):
            raise prior_sources_unavailable()
