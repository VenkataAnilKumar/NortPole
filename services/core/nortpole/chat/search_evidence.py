"""Resolve an explicit workspace Search selection into current citation evidence."""

from collections.abc import Callable, Sequence
from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from nortpole.chat.evidence_relevance import fitting_passage_span
from nortpole.chat.history_access import (
    EvidenceKey,
    prior_sources_unavailable,
    verify_indexed_history,
    workspace_evidence_keys,
)

from nortpole.configs.constants import DocumentSource, MessageType
from nortpole.context.search.forced_document_set import get_forced_document_set_names
from nortpole.context.search.models import (
    IndexFilters,
    PersonaSearchInfo,
    SearchDoc,
    TimeRange,
)
from nortpole.context.search.preprocessing.access_filters import (
    build_access_filters_for_user,
)
from nortpole.db.chat import is_selected_search_evidence
from nortpole.db.document_set import (
    fetch_document_sets_for_documents,
    filter_document_set_names_by_user_access,
    get_document_set_by_id_for_user,
)
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import ChatMessage, User
from nortpole.db.search_settings import get_current_search_settings
from nortpole.document_index.factory import get_default_document_index
from nortpole.document_index.interfaces import DocumentSectionRequest
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.file_store.models import ContextFileMetadata
from nortpole.file_store.utils import verify_user_files
from nortpole.server.features.search.drive_pilot import eligible_drive_library
from nortpole.server.features.search.workspace import (
    SUPPORTED_SOURCES,
    authorized_workspace_destinations,
    workspace_candidates,
)
from nortpole.server.query_and_chat.models import SearchEvidenceReference, SearchEvidenceSelection
from nortpole.utils.logger import setup_logger

logger = setup_logger()
LEGACY_PASSAGE_CHARS = 1800
PassageSpan = tuple[Annotated[int, Field(ge=0)], Annotated[int, Field(gt=0)]]


class SelectedSearchPassage(ContextFileMetadata):
    passage_span: PassageSpan | None = None


def _resolve_search_evidence(
    references: Sequence[SearchEvidenceReference],
    library_id: int | None,
    question: str,
    persona: PersonaSearchInfo,
    user: User,
    token_counter: Callable[[str], int],
    token_budget: int,
    *,
    expand_passages: bool = False,
) -> tuple[list[ContextFileMetadata], bool]:
    try:
        with get_session_with_current_tenant() as db:
            forced = get_forced_document_set_names(db)
            library_names = None
            if library_id is not None:
                library = get_document_set_by_id_for_user(
                    db, library_id, user, get_editable=False
                )
                if library is None or (forced and library.name not in forced):
                    return [], True
                if (
                    persona.document_set_names
                    and library.name not in persona.document_set_names
                ):
                    return [], True
                if not persona.document_set_names and (
                    persona.attached_document_ids or persona.hierarchy_node_ids
                ):
                    return [], True
                library_names = [library.name]
            elif persona.document_set_names:
                library_names = sorted(
                    filter_document_set_names_by_user_access(
                        db, persona.document_set_names, user
                    )
                )
                if not library_names:
                    return [], True
            access = build_access_filters_for_user(user, db)
            has_library_scope = library_names is not None
            sources = list(SUPPORTED_SOURCES)
            pilot_library_id = eligible_drive_library(user, db)
            if pilot_library_id is not None and (
                references or library_id == pilot_library_id
            ):
                sources.append(DocumentSource.GOOGLE_DRIVE)
            filters = IndexFilters(
                source_type=sources,
                access_control_list=access.access_control_list,
                cc_pair_access=access.cc_pair_access,
                forced_document_set=forced,
                document_set=library_names,
                attached_document_ids=None
                if has_library_scope
                else persona.attached_document_ids or None,
                hierarchy_node_ids=None
                if has_library_scope
                else persona.hierarchy_node_ids or None,
                updated_at_range=TimeRange(start=persona.search_start_date)
                if persona.search_start_date
                else None,
            )
            index = get_default_document_index(get_current_search_settings(db), None)
            if references:
                matches = index.id_based_retrieval(
                    [
                        DocumentSectionRequest(
                            document_id=item.document_id,
                            min_chunk_ind=item.chunk_id,
                            max_chunk_ind=item.chunk_id,
                        )
                        for item in references
                    ],
                    filters,
                )
                by_ref = {
                    (chunk.document_id, chunk.chunk_id): chunk
                    for chunk in matches
                    if not chunk.hidden
                }
                chunks = {
                    item.document_id: by_ref[(item.document_id, item.chunk_id)]
                    for item in references
                    if (item.document_id, item.chunk_id) in by_ref
                }
            else:
                matches, _ = workspace_candidates(question, filters, db, index)
                chunks = {}
                for chunk in matches:
                    if not chunk.hidden:
                        chunks.setdefault(chunk.document_id, chunk)
            destinations = authorized_workspace_destinations(chunks, user, db)
            if destinations and (library_names or forced):
                memberships = dict(
                    fetch_document_sets_for_documents(list(destinations), db)
                )
                for doc_id in list(destinations):
                    names = set(memberships.get(doc_id, ()))
                    if (library_names and names.isdisjoint(library_names)) or (
                        forced and names.isdisjoint(forced)
                    ):
                        del destinations[doc_id]
    except Exception as error:
        logger.warning("Could not retrieve Search evidence (%s)", type(error).__name__)
        raise NortPoleError(
            NortPoleErrorCode.SERVICE_UNAVAILABLE,
            "Search evidence is temporarily unavailable. Try again.",
        ) from None

    previous_spans = {
        item.document_id: item.passage_span for item in references
        if isinstance(item, SearchEvidenceSource)
    }
    evidence: list[ContextFileMetadata] = []
    full_passages_fit = expand_passages and sum(
        token_counter(chunk.content.strip()) + token_counter(chunk.title or chunk.semantic_identifier) + 32
        for doc_id, chunk in chunks.items() if doc_id in destinations
    ) <= token_budget
    remaining = sum(doc_id in destinations for doc_id in chunks)
    for doc_id, chunk in chunks.items():
        if doc_id not in destinations:
            continue
        title = chunk.title or chunk.semantic_identifier
        overhead = token_counter(title) + 32
        span = previous_spans.get(doc_id)
        if expand_passages:
            passage_budget = token_budget if full_passages_fit else token_budget // remaining
            span = fitting_passage_span(
                chunk.content, question, token_counter, passage_budget - overhead,
            )
            remaining -= 1
            if span is None:
                continue
        if span is not None:
            start, end = span
            if not 0 <= start < end <= len(chunk.content):
                continue
            text = chunk.content[start:end].strip()
        else:
            text = chunk.content[:LEGACY_PASSAGE_CHARS].strip()
        tokens = token_counter(text) + overhead
        if not text or tokens > token_budget:
            continue
        url = destinations[doc_id]
        source_chunk = chunk.model_copy(
            update={"source_links": {0: url} if url else None}
        )
        doc = SearchDoc.from_chunks_or_sections([source_chunk])[0]
        doc.selected_evidence = True
        evidence.append(
            SelectedSearchPassage(
                file_id=doc_id, filename=title, file_content=text, source_document=doc,
                passage_span=span,
            )
        )
        token_budget -= tokens
        if len(evidence) == 5:
            break
    return evidence, bool(references) and len(evidence) < len(
        references
    )


def resolve_search_evidence(
    selection: SearchEvidenceSelection,
    question: str,
    persona: PersonaSearchInfo,
    user: User,
    token_counter: Callable[[str], int],
    token_budget: int,
    *,
    expand_passages: bool = False,
) -> tuple[list[ContextFileMetadata], bool]:
    return _resolve_search_evidence(
        selection.documents, selection.library_id, question, persona, user,
        token_counter, token_budget,
        expand_passages=expand_passages,
    )


def resolve_library_passage(
    reference: SearchEvidenceReference,
    library_id: int,
    persona: PersonaSearchInfo,
    user: User,
) -> ContextFileMetadata | None:
    passages, _ = _resolve_search_evidence(
        [reference], library_id, "", persona, user, len, 8192,
    )
    return passages[0] if passages else None


class SearchEvidenceSource(SearchEvidenceReference):
    source_type: DocumentSource
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    passage_span: PassageSpan | None = None


class SearchEvidenceProvenance(BaseModel):
    library_id: int | None = Field(default=None, gt=0)
    sources: list[SearchEvidenceSource] = Field(default_factory=list, max_length=5)
    context_files: dict[UUID, str] = Field(default_factory=dict)
    indexed_sources: list[EvidenceKey] = Field(default_factory=list)
    knowledge_libraries: list[str] = Field(default_factory=list)
    tool_sources: list[EvidenceKey] = Field(default_factory=list)

    @classmethod
    def capture(
        cls, evidence: Sequence[ContextFileMetadata], library_id: int | None
    ) -> "SearchEvidenceProvenance":
        sources = []
        for item in evidence:
            if item.source_document is None:
                raise ValueError("Search evidence must have a source document")
            source = item.source_document
            # Include the text and title the model received, without storing either again.
            fingerprint = sha256(
                f"{len(item.filename)}:{item.filename}{item.file_content}".encode()
            ).hexdigest()
            sources.append(SearchEvidenceSource(
                document_id=source.document_id,
                chunk_id=source.chunk_ind,
                source_type=source.source_type,
                fingerprint=fingerprint,
                passage_span=item.passage_span if isinstance(item, SelectedSearchPassage) else None,
            ))
        return cls(library_id=library_id, sources=sources)


def verify_search_evidence_history(
    history: Sequence[ChatMessage],
    persona: PersonaSearchInfo,
    user: User,
    *,
    db: Session | None = None,
    context_files: dict[UUID, str] | None = None,
    project_id: int | None = None,
    temporary: dict[str, dict] | None = None,
    recheck_drive: bool = False,
) -> None:
    """Check selected ancestry before its answers, tool context or summary are reused."""
    verified: set[str] = set()
    tracked: set[EvidenceKey] = set()
    indexed: set[EvidenceKey] = set()
    from_libraries: dict[tuple[str, ...], set[EvidenceKey]] = {}
    current_files = context_files or {}
    resolved_file_ids = {str(file_id) for file_id in current_files} | set(current_files.values())
    for message in history:
        if message.message_type != MessageType.ASSISTANT:
            continue
        raw = (temporary or {}).get(str(message.id), message.search_evidence_provenance)
        if raw is not None:
            try:
                record = SearchEvidenceProvenance.model_validate(raw)
            except ValidationError as error:
                raise prior_sources_unavailable() from error
            if record.context_files.items() - current_files.items():
                raise prior_sources_unavailable()
            if record.knowledge_libraries:
                libraries = tuple(sorted(record.knowledge_libraries))
                from_libraries.setdefault(libraries, set()).update(record.indexed_sources)
            indexed.update(record.indexed_sources)
            indexed.update(record.tool_sources)
            evidence = record.model_dump_json(include={"library_id", "sources"})
            if record.sources and evidence not in verified:
                current, incomplete = _resolve_search_evidence(
                    record.sources, record.library_id, "", persona, user,
                    lambda _: 0, 5 * 32,
                )
                if incomplete or not current or record.sources != SearchEvidenceProvenance.capture(
                    current, record.library_id
                ).sources:
                    raise prior_sources_unavailable()
                verified.add(evidence)
                tracked.update(
                    (item.document_id, item.chunk_id, item.source_type)
                    for item in record.sources
                )
        for doc in message.search_docs:
            if is_selected_search_evidence(doc) and (
                doc.document_id, doc.chunk_ind, doc.source_type
            ) not in tracked:
                raise prior_sources_unavailable()
        indexed.update(workspace_evidence_keys(message.search_docs))
    remaining = {
        key for key in indexed - tracked if key[0] not in resolved_file_ids
    }
    if db is not None:
        indexed_ids = {doc_id for doc_id, _, _ in remaining}
        cited_attachments = {
            file["id"]: file
            for message in history
            if message.message_type == MessageType.USER
            for file in message.files or []
            if file["id"] in indexed_ids
        }
        if cited_attachments:
            try:
                verify_user_files(list(cited_attachments.values()), user.id, db, project_id)
            except (ValueError, HTTPException) as error:
                raise prior_sources_unavailable() from error
            remaining = {key for key in remaining if key[0] not in cited_attachments}
        checked: set[EvidenceKey] = set()
        for libraries, keys in from_libraries.items():
            scoped = {
                key for key in keys
                if key[0] not in resolved_file_ids and key[0] not in cited_attachments
            }
            verify_indexed_history(
                scoped, persona, user, db, selected_libraries=libraries, recheck_drive=recheck_drive,
            )
            checked.update(scoped)
        remaining -= checked
        verify_indexed_history(remaining, persona, user, db, recheck_drive=recheck_drive)
