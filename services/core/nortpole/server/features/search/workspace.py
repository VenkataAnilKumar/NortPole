"""Indexed Knowledge search for the workspace."""

from datetime import datetime
from hashlib import sha256
from math import isfinite
from urllib.parse import quote, urlsplit
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import String, and_, cast, select
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.configs.constants import DocumentSource
from nortpole.connectors.file.metadata import file_document_id
from nortpole.context.search.enums import QueryType
from nortpole.context.search.forced_document_set import get_forced_document_set_names
from nortpole.context.search.models import IndexFilters, InferenceChunk, TimeRange
from nortpole.context.search.preprocessing.access_filters import (
    build_access_filters_for_user,
)
from nortpole.context.search.utils import get_query_embedding
from nortpole.db.connector_credential_pair import build_user_cc_pair_access_filter
from nortpole.db.document_set import (
    fetch_all_document_sets_for_user,
    fetch_document_sets_for_documents,
    get_document_set_by_id_for_user,
)
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import (
    AccessType,
    ConnectorCredentialPairStatus,
    Permission,
    UserFileStatus,
)
from nortpole.db.models import (
    Connector,
    ConnectorCredentialPair,
    Document,
    DocumentByConnectorCredentialPair,
    User,
    UserFile,
)
from nortpole.db.search_settings import get_current_search_settings
from nortpole.document_index.factory import get_default_document_index
from nortpole.document_index.interfaces import DocumentIndex
from nortpole.redis.redis_pool import get_redis_client
from nortpole.server.api_key_usage import check_api_key_usage
from nortpole.server.features.search.drive_pilot import (
    eligible_drive_library,
    live_drive_destinations,
)
from nortpole.server.utils_vector_db import require_vector_db
from nortpole.utils.logger import setup_logger
from shared_configs.contextvars import get_current_tenant_id

router = APIRouter()
logger = setup_logger()
CANDIDATE_LIMIT = 300
PAGE_SIZE = 20
CURSOR_TTL_SECONDS = 300
WORKSPACE_SOURCES = (DocumentSource.FILE, DocumentSource.INGESTION_API)
SUPPORTED_SOURCES = (*WORKSPACE_SOURCES, DocumentSource.USER_FILE)


class WorkspaceSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2048)
    library_id: int | None = Field(default=None, gt=0)
    source: DocumentSource | None = None
    updated_since: datetime | None = None
    cursor: UUID | None = None
    page_size: int = Field(default=PAGE_SIZE, ge=1, le=CANDIDATE_LIMIT)


class WorkspaceSearchResult(BaseModel):
    id: str
    chunk_id: int
    title: str
    source: DocumentSource
    excerpt: str
    updated_at: datetime | None
    url: str | None


class WorkspaceSearchResponse(BaseModel):
    results: list[WorkspaceSearchResult]
    next_cursor: UUID | None = None
    limited: bool = False
    lexical_only: bool = False


class LibraryOption(BaseModel):
    id: int
    name: str
    drive_search: bool = False


class SearchContinuation(BaseModel):
    scope: str
    document_ids: list[str]
    limited: bool


@router.get("/workspace/libraries")
def workspace_search_libraries(
    response: Response,
    user: User = Depends(require_permission(Permission.READ_SEARCH)),
    db: Session = Depends(get_session),
) -> list[LibraryOption]:
    response.headers["Cache-Control"] = "private, no-store"
    forced = get_forced_document_set_names(db)
    drive_library_id = eligible_drive_library(user, db)
    return sorted(
        (
            LibraryOption(
                id=library.id,
                name=library.name,
                drive_search=library.id == drive_library_id,
            )
            for library in fetch_all_document_sets_for_user(
                db, user, get_editable=False
            )
            if forced is None or library.name in forced
        ),
        key=lambda option: (option.name.casefold(), option.id),
    )


def _file_url(file_id: str) -> str:
    return f"/api/chat/file/{quote(file_id, safe='')}?fresh=true"


def _external_url(url: str | None) -> str | None:
    if not url or any(ord(char) < 32 or char == "\\" for char in url):
        return None
    try:
        parts = urlsplit(url)
        if (
            parts.scheme in ("http", "https")
            and parts.hostname
            and not parts.username
            and not parts.password
        ):
            return url
    except ValueError:
        pass
    return None


def authorized_workspace_destinations(
    chunks: dict[str, InferenceChunk],
    user: User,
    db: Session,
) -> dict[str, str | None]:
    """Check current ownership and workspace-managed pair access after index retrieval."""
    personal_ids = [
        doc_id
        for doc_id, chunk in chunks.items()
        if chunk.source_type == DocumentSource.USER_FILE
    ]
    destinations: dict[str, str | None] = (
        {
            str(file_id): _file_url(str(file_id))
            for file_id in db.scalars(
                select(UserFile.id).where(
                    cast(UserFile.id, String).in_(personal_ids),
                    UserFile.user_id == user.id,
                    UserFile.incognito.is_(False),
                    UserFile.status == UserFileStatus.COMPLETED,
                )
            )
        }
        if personal_ids
        else {}
    )

    destinations.update(
        live_drive_destinations(
            [
                doc_id
                for doc_id, chunk in chunks.items()
                if chunk.source_type == DocumentSource.GOOGLE_DRIVE
            ],
            user,
            db,
        )
    )

    upload_ids = [
        doc_id
        for doc_id, chunk in chunks.items()
        if chunk.source_type in WORKSPACE_SOURCES
    ]
    if not upload_ids:
        return destinations
    pairs = DocumentByConnectorCredentialPair
    connector_pair = ConnectorCredentialPair
    rows = db.execute(
        select(
            Document.id,
            Document.link,
            Document.file_id,
            Connector.connector_specific_config,
        )
        .join(pairs, pairs.id == Document.id)
        .join(
            connector_pair,
            and_(
                connector_pair.connector_id == pairs.connector_id,
                connector_pair.credential_id == pairs.credential_id,
            ),
        )
        .join(Connector, Connector.id == pairs.connector_id)
        .where(
            Document.id.in_(upload_ids),
            Document.hidden.is_(False),
            pairs.has_been_indexed.is_(True),
            Connector.source.in_(WORKSPACE_SOURCES),
            connector_pair.status != ConnectorCredentialPairStatus.DELETING,
            connector_pair.perm_sync_pending_since.is_(None),
            connector_pair.access_type.notin_(AccessType.perm_synced_types()),
            build_user_cc_pair_access_filter(user.id),
        )
        .order_by(connector_pair.id)
    )
    for doc_id, link, file_id, config in rows:
        if destinations.get(doc_id):
            continue
        if not file_id:
            file_id = next(
                (
                    location
                    for location in (config or {}).get("file_locations", [])
                    if isinstance(location, str)
                    and file_document_id(location, None) == doc_id
                ),
                None,
            )
        destinations[doc_id] = _file_url(file_id) if file_id else _external_url(link)
    return destinations


def _rank_documents(chunks: list[InferenceChunk]) -> dict[str, InferenceChunk]:
    def rank(chunk: InferenceChunk) -> tuple[float, str, int]:
        score = (
            chunk.score if chunk.score is not None and isfinite(chunk.score) else 0.0
        )
        return (-score, chunk.document_id, chunk.chunk_id)

    ranked: dict[str, InferenceChunk] = {}
    for chunk in sorted(chunks, key=rank):
        ranked.setdefault(chunk.document_id, chunk)
    return ranked


def _excerpt(chunk: InferenceChunk) -> str:
    text = chunk.match_highlights[0] if chunk.match_highlights else chunk.content
    return " ".join(text.replace("<hi>", "").replace("</hi>", "").split())[:420]


def workspace_candidates(
    query: str, filters: IndexFilters, db: Session, index: DocumentIndex
) -> tuple[list[InferenceChunk], bool]:
    lexical_only = False
    try:
        embedding = get_query_embedding(query, db_session=db)
    except Exception as exc:
        logger.info(
            "Workspace search falling back to lexical retrieval (%s)",
            type(exc).__name__,
        )
        lexical_only = True
    try:
        if lexical_only:
            matches = index.keyword_retrieval(query, filters, CANDIDATE_LIMIT)
        else:
            matches = index.hybrid_retrieval(
                query, embedding, None, QueryType.SEMANTIC, filters, CANDIDATE_LIMIT
            )
    except Exception as exc:
        logger.warning("Workspace search index unavailable (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Search is temporarily unavailable."
        ) from None

    return matches, lexical_only


@router.post(
    "/workspace",
    dependencies=[Depends(require_vector_db), Depends(check_api_key_usage)],
)
def search_workspace_knowledge(
    request: WorkspaceSearchRequest,
    response: Response,
    user: User = Depends(require_permission(Permission.READ_SEARCH)),
    db: Session = Depends(get_session),
) -> WorkspaceSearchResponse:
    response.headers["Cache-Control"] = "private, no-store"
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Enter a search query.")
    scope = sha256(
        f"{user.id}:{request.model_dump_json(exclude={'cursor', 'page_size'}, exclude_none=True)}".encode()
    ).hexdigest()
    store = get_redis_client()
    continuation = None
    if request.cursor is not None:
        stored = store.get(f"workspace-search:{request.cursor}")
        continuation = (
            SearchContinuation.model_validate_json(stored) if stored else None
        )
        if continuation is None or continuation.scope != scope:
            raise HTTPException(
                status_code=410, detail="These results expired. Run the search again."
            )

    forced = get_forced_document_set_names(db)
    library_names = None
    if request.library_id is not None:
        library = get_document_set_by_id_for_user(
            db, request.library_id, user, get_editable=False
        )
        if library is None or (forced is not None and library.name not in forced):
            return WorkspaceSearchResponse(results=[])
        library_names = [library.name]
    allowed_sources = list(SUPPORTED_SOURCES)
    if request.library_id is not None and request.library_id == eligible_drive_library(
        user, db
    ):
        allowed_sources.append(DocumentSource.GOOGLE_DRIVE)
    sources = [request.source] if request.source else allowed_sources
    if not set(sources).issubset(allowed_sources):
        return WorkspaceSearchResponse(results=[])

    access = build_access_filters_for_user(user, db)
    filters = IndexFilters(
        source_type=sources,
        document_set=library_names,
        forced_document_set=forced,
        updated_at_range=TimeRange(start=request.updated_since)
        if request.updated_since
        else None,
        access_control_list=access.access_control_list,
        cc_pair_access=access.cc_pair_access,
        tenant_id=get_current_tenant_id(),
    )
    index = get_default_document_index(get_current_search_settings(db), None)
    matches, lexical_only = workspace_candidates(query, filters, db, index)

    ranked = _rank_documents(matches)
    destinations = authorized_workspace_destinations(ranked, user, db)
    if destinations and (library_names or forced):
        memberships = dict(fetch_document_sets_for_documents(list(destinations), db))
        destinations = {
            doc_id: url
            for doc_id, url in destinations.items()
            if (
                not library_names
                or not set(library_names).isdisjoint(memberships.get(doc_id, ()))
            )
            and (not forced or not set(forced).isdisjoint(memberships.get(doc_id, ())))
        }
    window = continuation.document_ids if continuation else list(ranked)
    available = [
        doc_id for doc_id in window if doc_id in destinations and doc_id in ranked
    ]
    limited = len(matches) >= CANDIDATE_LIMIT and ranked.keys() <= destinations.keys()
    if continuation is not None:
        limited = limited and continuation.limited
    next_cursor = None
    if len(available) > request.page_size:
        next_cursor = uuid4()
        state = SearchContinuation(
            scope=scope, document_ids=available[request.page_size :], limited=limited
        )
        store.set(
            f"workspace-search:{next_cursor}",
            state.model_dump_json(),
            ex=CURSOR_TTL_SECONDS,
        )
    return WorkspaceSearchResponse(
        results=[
            WorkspaceSearchResult(
                id=doc_id,
                chunk_id=ranked[doc_id].chunk_id,
                title=ranked[doc_id].title or ranked[doc_id].semantic_identifier,
                source=ranked[doc_id].source_type,
                excerpt=_excerpt(ranked[doc_id]),
                updated_at=ranked[doc_id].updated_at,
                url=destinations[doc_id],
            )
            for doc_id in available[: request.page_size]
        ],
        next_cursor=next_cursor,
        limited=limited,
        lexical_only=lexical_only,
    )
