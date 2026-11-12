"""Gather evidence for a task run, as the task's owner.

Retrieval uses the owner's own access filters (groups, the search-time source
check), so a run can only see what its owner may see. Without a retrieval
index (lite mode) there is nothing to search and the run drafts an explicit
evidence gap instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from evolvxsi.configs.app_configs import DISABLE_VECTOR_DB
from evolvxsi.context.search.models import IndexFilters, InferenceChunk
from evolvxsi.context.search.preprocessing.access_filters import build_access_filters_for_user
from evolvxsi.db.models import User

MAX_SOURCES = 6
MAX_PASSAGE = 1200


@dataclass(frozen=True)
class Evidence:
    n: int
    doc_id: str
    title: str
    link: str | None
    passage: str


def _search(db_session: Session, user: User, query: str, limit: int) -> list[InferenceChunk]:
    from evolvxsi.db.search_settings import get_active_search_settings
    from evolvxsi.document_index.factory import get_default_document_index

    settings = get_active_search_settings(db_session)
    index = get_default_document_index(settings.primary, settings.secondary)
    access = build_access_filters_for_user(user, db_session)
    filters = IndexFilters(access_control_list=access.access_control_list, cc_pair_access=access.cc_pair_access)
    return index.keyword_retrieval(query=query, filters=filters, num_to_retrieve=limit * 3)


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
