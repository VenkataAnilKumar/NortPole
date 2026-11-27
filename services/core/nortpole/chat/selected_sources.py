"""Prepare explicitly selected sources with the existing chat search and citation model."""

from collections.abc import Callable, Collection
from itertools import zip_longest
from math import log

from nortpole.chat.evidence_relevance import (
    comparison_topics,
    evidence_phrases,
    evidence_terms,
    lookup_intent,
    sentence_spans,
    term_overlap,
)
from nortpole.chat.history_access import verify_indexed_history
from nortpole.chat.verified_comparison import is_comparison_question
from nortpole.configs.app_configs import DISABLE_VECTOR_DB
from nortpole.configs.constants import DocumentSource
from nortpole.context.search.models import (
    BaseFilters,
    ChunkSearchRequest,
    InferenceChunk,
    PersonaSearchInfo,
    SearchDoc,
)
from nortpole.context.search.pipeline import merge_individual_chunks, search_pipeline
from nortpole.context.search.preprocessing.access_filters import (
    build_access_filters_for_user,
)
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.db.search_settings import get_current_search_settings
from nortpole.document_index.factory import get_default_document_index
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.federated_connectors.federated_retrieval import (
    get_federated_retrieval_functions,
)
from nortpole.file_store.models import ChatFileInput, ChatFileType, ContextFileMetadata
from nortpole.file_store.utils import get_default_file_store
from nortpole.natural_language_processing.search_nlp_models import EmbeddingModel
from nortpole.server.features.search.drive_pilot import live_drive_destinations
from nortpole.utils.logger import setup_logger
from nortpole.utils.threadpool_concurrency import run_functions_tuples_in_parallel
from shared_configs.configs import MODEL_SERVER_HOST, MODEL_SERVER_PORT

logger = setup_logger()
MAX_INLINE_CSV_BYTES = 12_000
MAX_SELECTED_KNOWLEDGE_HITS = 5
MAX_INDEXED_KNOWLEDGE_CANDIDATES = 20
MAX_SELECTED_PASSAGE_CHARS = 3_000


def load_small_csv_sources(
    inputs: list[ChatFileInput],
    attached_ids: Collection[str],
    token_counter: Callable[[str], int],
    token_budget: int,
) -> list[ContextFileMetadata]:
    """Read whole small CSVs so quoted fields and rows are never truncated."""
    if token_budget <= 0:
        return []
    store = get_default_file_store()
    sources: list[ContextFileMetadata] = []
    for item in inputs:
        descriptor = item.descriptor
        file_id = descriptor["id"]
        name = descriptor.get("name") or ""
        if (
            file_id not in attached_ids
            or descriptor["type"] != ChatFileType.TABULAR
            or not name.lower().endswith(".csv")
        ):
            continue

        try:
            size = store.get_file_size(file_id)
            if size is None or size > MAX_INLINE_CSV_BYTES:
                continue
            with store.read_file(file_id, mode="b") as source:
                raw = source.read(MAX_INLINE_CSV_BYTES + 1)
            if len(raw) > MAX_INLINE_CSV_BYTES:
                continue
            contents = raw.decode("utf-8-sig").strip()
        except (FileNotFoundError, UnicodeError) as error:
            raise NortPoleError(
                NortPoleErrorCode.INVALID_INPUT,
                f'Could not read the selected CSV "{name}". Reattach it as a UTF-8 CSV.',
            ) from error
        except Exception as error:
            logger.exception("Could not load selected CSV")
            raise NortPoleError(
                NortPoleErrorCode.INVALID_INPUT,
                f'Could not read the selected CSV "{name}". Reattach it and try again.',
            ) from error
        if not contents:
            raise NortPoleError(
                NortPoleErrorCode.INVALID_INPUT, f'The selected CSV "{name}" is empty.'
            )
        # Include room for the title and the prompt's document wrapper.
        tokens = token_counter(contents) + token_counter(name) + 32
        if tokens <= token_budget:
            sources.append(
                ContextFileMetadata(file_id=file_id, filename=name, file_content=contents)
            )
            token_budget -= tokens
    return sources


def _prioritize_distinct_documents(chunks: list[InferenceChunk]) -> list[InferenceChunk]:
    first_by_document: dict[str, InferenceChunk] = {}
    remaining: list[InferenceChunk] = []
    for chunk in chunks:
        if chunk.document_id in first_by_document:
            remaining.append(chunk)
        else:
            first_by_document[chunk.document_id] = chunk
    return [*first_by_document.values(), *remaining]


def _rank_comparison_passages(
    topics: list[str], candidates: list[list[InferenceChunk]], *, question: str,
) -> list[InferenceChunk]:
    chunks = list(dict.fromkeys(chunk for matches in candidates for chunk in matches))
    topic_phrases = set().union(*(evidence_phrases(topic) for topic in topics))
    subjects = evidence_phrases(question) - topic_phrases
    passage_terms: dict[InferenceChunk, list[tuple[set[str], bool]]] = {}
    chunk_terms: dict[InferenceChunk, set[str]] = {}
    for chunk in chunks:
        chunk_terms[chunk] = evidence_terms(chunk.content)
        sentences = sentence_spans(chunk.content)
        # A rule can name the subject in one sentence and its condition in the next.
        passages = []
        for index, (start, end) in enumerate(sentences):
            if index + 1 < len(sentences):
                end = sentences[index + 1][1]
            nearby_text = chunk.content[max(0, start - 420):end + 240]
            passages.append((
                evidence_terms(chunk.content[start:end]),
                bool(subjects & evidence_phrases(nearby_text)),
            ))
        passage_terms[chunk] = passages
    rankings: list[list[InferenceChunk]] = []
    for topic, matches in zip(topics, candidates[:len(topics)], strict=True):
        terms = evidence_terms(topic)
        # Rare words distinguish the requested action from generic topic matches.
        weights = {
            term: 1 + log((len(chunks) + 1) / (
                1 + sum(bool(term_overlap({term}, words)) for words in chunk_terms.values())
            ))
            for term in sorted(terms)
        }
        focused_order = {chunk: rank for rank, chunk in enumerate(matches)}
        scores: dict[InferenceChunk, float] = {}
        for chunk, passages in passage_terms.items():
            scores[chunk] = 0.0
            for passage, matches_subject in passages:
                score = sum(weight * term_overlap({term}, passage) for term, weight in weights.items())
                if score and matches_subject:
                    score += 2
                scores[chunk] = max(scores[chunk], score)
        rankings.append(sorted(
            chunks, key=lambda chunk: (-scores[chunk], focused_order.get(chunk, len(matches))),
        ))
    return list(dict.fromkeys(chunk for group in zip(*rankings, strict=True) for chunk in group))


def _authorize_drive_passages(
    candidates: list[list[InferenceChunk]], user: User, libraries: list[str],
) -> list[list[InferenceChunk]]:
    ordered_ids = list(dict.fromkeys(
        chunk.document_id for group in zip_longest(*candidates) for chunk in group
        if chunk is not None and chunk.source_type == DocumentSource.GOOGLE_DRIVE
    ))
    if not ordered_ids:
        return candidates
    with get_session_with_current_tenant() as session:
        destinations = live_drive_destinations(ordered_ids, user, session, library_names=libraries)

    authorized = []
    for matches in candidates:
        passages = []
        for chunk in matches:
            if chunk.source_type != DocumentSource.GOOGLE_DRIVE:
                passages.append(chunk)
            elif link := destinations.get(chunk.document_id):
                passages.append(chunk.model_copy(update={"source_links": {0: link}}))
        authorized.append(passages)
    return authorized


def retrieve_selected_knowledge(
    query: str,
    filters: BaseFilters,
    persona: PersonaSearchInfo,
    user: User,
    token_counter: Callable[[str], int],
    token_budget: int,
    *,
    allow_empty: bool = False,
    indexed_only: bool = False,
    recheck_drive: bool = False,
) -> list[ContextFileMetadata]:
    """Retrieve under the acting user's ACL and existing chat search scope."""
    libraries = filters.document_set or []
    if not libraries:
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT, "Choose a Knowledge library before sending."
        )
    if persona.document_set_names and not set(libraries).issubset(
        persona.document_set_names
    ):
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "A selected Knowledge library is outside this agent's search scope.",
        )

    if filters.source_type == []:
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT,
            "Enable a search source to read the selected Knowledge libraries.",
        )

    # The index combines those persona attachments and the selected libraries
    # with OR. Explicitly selected libraries own the scope of this prefetch.
    selected_scope = persona.model_copy(
        update={"attached_document_ids": [], "hierarchy_node_ids": []}
    )
    try:
        if DISABLE_VECTOR_DB:
            raise RuntimeError("Knowledge retrieval is disabled")
        with get_session_with_current_tenant() as session:
            settings = get_current_search_settings(session)
            if settings is None:
                raise RuntimeError("Knowledge search settings are unavailable")
            index = get_default_document_index(settings, None)
            embedding = EmbeddingModel.from_db_model(
                search_settings=settings,
                server_host=MODEL_SERVER_HOST,
                server_port=MODEL_SERVER_PORT,
            )
            acl = build_access_filters_for_user(user, session)
            federated = [] if indexed_only else get_federated_retrieval_functions(
                db_session=session,
                user_id=user.id,
                source_types=filters.source_type,
                document_set_names=libraries,
            )
        def search(text: str) -> list[InferenceChunk]:
            return search_pipeline(
                ChunkSearchRequest(
                    query=text,
                    user_selected_filters=filters,
                    limit=(
                        MAX_INDEXED_KNOWLEDGE_CANDIDATES if indexed_only
                        else MAX_SELECTED_KNOWLEDGE_HITS
                    ),
                ),
                index,
                user,
                selected_scope,
                acl_filters=acl,
                embedding_model=embedding,
                prefetched_federated_retrieval_infos=federated or [],
            )

        topics = comparison_topics(query) if indexed_only and is_comparison_question(query) else []
        # Research uses the same operation names to find and verify evidence.
        intent = lookup_intent(query) if recheck_drive and not topics else None
        if topics:
            queries = list(dict.fromkeys([*topics, query]))
            candidates = run_functions_tuples_in_parallel([(search, (text,)) for text in queries])
        else:
            candidates = [search(intent.query if intent is not None else query)]
        if recheck_drive:
            candidates = _authorize_drive_passages(candidates, user, libraries)
        chunks = _rank_comparison_passages(topics, candidates, question=query) if topics else candidates[0]
    except NortPoleError:
        raise
    except Exception as error:
        logger.exception("Could not retrieve selected Knowledge")
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT,
            f'Could not read the selected Knowledge libraries ({", ".join(libraries)}). Try again.',
        ) from error

    if indexed_only:
        # Keep ranked passages intact. Merging by position can truncate the best
        # chunk, and repeats can fill the budget before a second source fits.
        ranked = _prioritize_distinct_documents(chunks)
        passages = zip(
            (chunk.content for chunk in ranked),
            SearchDoc.from_chunks_or_sections(ranked),
            strict=True,
        )
    else:
        sections = merge_individual_chunks(chunks)
        passages = zip(
            (section.combined_content for section in sections),
            SearchDoc.from_chunks_or_sections(sections),
            strict=True,
        )
    sources: list[ContextFileMetadata] = []
    indexed_keys = set()
    for passage, doc in passages:
        text = passage[:MAX_SELECTED_PASSAGE_CHARS].strip()
        tokens = token_counter(text) + token_counter(doc.semantic_identifier) + 32
        if text and tokens <= token_budget:
            sources.append(
                ContextFileMetadata(
                    file_id=doc.document_id,
                    filename=doc.semantic_identifier,
                    file_content=text,
                    source_document=doc,
                )
            )
            token_budget -= tokens
            if indexed_only:
                indexed_keys.add((doc.document_id, doc.chunk_ind, doc.source_type))
            if len(sources) == MAX_SELECTED_KNOWLEDGE_HITS:
                break
    if indexed_keys:
        with get_session_with_current_tenant() as session:
            verify_indexed_history(
                indexed_keys, selected_scope, user, session, selected_libraries=tuple(libraries),
            )
    if not sources and not allow_empty:
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT,
            f'No usable excerpts were found in the selected Knowledge libraries ({", ".join(libraries)}). Refine the question or pick another library.',
        )
    return sources
