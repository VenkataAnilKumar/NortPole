"""Gather evidence for a task run, as the task's owner.

Retrieval uses the owner's own access filters (groups, the search-time source
check), so a run can only see what its owner may see. Without a retrieval
index (lite mode) there is nothing to search and the run drafts an explicit
evidence gap instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from nortpole.configs.app_configs import DISABLE_VECTOR_DB
from nortpole.context.search.models import IndexFilters, InferenceChunk
from nortpole.context.search.preprocessing.access_filters import build_access_filters_for_user
from nortpole.db.models import User
from nortpole.utils.logger import setup_logger

logger = setup_logger()

# Candidates handed to the relevance judge: one model call each, so kept small.
MAX_SOURCES = 4
MAX_PASSAGE = 1200


@dataclass(frozen=True)
class Evidence:
    n: int
    doc_id: str
    title: str
    link: str | None
    passage: str


def _merge(primary: list[InferenceChunk], backup: list[InferenceChunk]) -> list[InferenceChunk]:
    """Meaning-based hits first, then keyword hits the first list missed."""
    seen = {c.document_id for c in primary}
    return primary + [c for c in backup if c.document_id not in seen]


def _search(db_session: Session, user: User, query: str, limit: int) -> list[InferenceChunk]:
    from nortpole.context.search.utils import get_query_embedding
    from nortpole.db.search_settings import get_active_search_settings
    from nortpole.document_index.factory import get_default_document_index

    settings = get_active_search_settings(db_session)
    index = get_default_document_index(settings.primary, settings.secondary)
    access = build_access_filters_for_user(user, db_session)
    filters = IndexFilters(access_control_list=access.access_control_list, cc_pair_access=access.cc_pair_access)
    keyword = index.keyword_retrieval(query=query, filters=filters, num_to_retrieve=limit * 3)
    try:
        # The deployment's own embedding model, so the vector matches the index.
        vector = get_query_embedding(query, db_session)
        semantic = index.semantic_retrieval(query_embedding=vector, filters=filters, num_to_retrieve=limit * 3)
    except Exception:
        logger.exception("task evidence: embedding unavailable, using keyword search only")
        return keyword
    return _merge(semantic, keyword)


def chunks_to_evidence(chunks: list[InferenceChunk], limit: int = MAX_SOURCES) -> list[Evidence]:
    """One entry per document, best first, numbered from 1."""
    out: list[Evidence] = []
    seen: set[str] = set()
    for c in chunks:
        if c.document_id in seen:
            continue
        seen.add(c.document_id)
        link = next(iter((c.source_links or {}).values()), None)
        out.append(
            Evidence(
                n=len(out) + 1,
                doc_id=c.document_id,
                title=c.semantic_identifier or c.title or c.document_id,
                link=link,
                passage=(c.content or c.blurb or "")[:MAX_PASSAGE],
            )
        )
        if len(out) >= limit:
            break
    return out


def gather_evidence(db_session: Session, user: User, query: str, limit: int = MAX_SOURCES) -> list[Evidence]:
    if DISABLE_VECTOR_DB:
        return []
    return chunks_to_evidence(_search(db_session, user, query, limit), limit)
