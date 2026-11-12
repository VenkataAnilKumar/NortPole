"""Permission harness against a real OpenSearch (A5 step 2).

Writes the fixed A5 test set into a throwaway index with each document's real
access list, then runs the core's own keyword and semantic retrieval as each
test viewer. What comes back must match the access rules exactly.

Needs a running OpenSearch. Skipped when none answers. Embeddings are
deterministic test vectors (no model), so this checks access filtering, not
answer quality. Run with, for example:

    OPENSEARCH_HOST=127.0.0.1 OPENSEARCH_USE_SSL=false \\
        pytest tests/evolvxsi_integration/test_retrieval_acl.py
"""

import hashlib
import json
import os
import uuid
from pathlib import Path

import pytest
import requests

from evolvxsi.access.models import DocumentAccess
from evolvxsi.configs.constants import DocumentSource
from evolvxsi.connectors.models import Document, TextSection
from evolvxsi.context.search.models import IndexFilters
from evolvxsi.db.enums import VectorQuantization
from evolvxsi.document_index.interfaces import IndexingMetadata, TenantState
from evolvxsi.document_index.opensearch.opensearch_document_index import (
    OpenSearchDocumentIndex,
)
from evolvxsi.indexing.models import ChunkEmbedding, DocMetadataAwareIndexChunk
from evolvxsi.knowledge_access.decisions import SourceDocument, Viewer, may_see, viewer_acl

DIM = 16
TENANT = "public"
TEST_SET = json.loads(
    (Path(__file__).parents[1] / "unit/evolvxsi/knowledge_access/a5_test_set.json").read_text()
)


def _opensearch_up() -> bool:
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = os.environ.get("OPENSEARCH_REST_API_PORT", "9200")
    try:
        return requests.get(f"http://{host}:{port}", timeout=2).ok
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _opensearch_up(), reason="no OpenSearch running")


def _vector(text: str) -> list[float]:
    """Deterministic test vector. Not semantic; only gives each chunk a valid embedding."""
    digest = hashlib.sha256(text.encode()).digest()
    raw = [b / 255.0 + 0.01 for b in digest[:DIM]]
    norm = sum(v * v for v in raw) ** 0.5
    return [v / norm for v in raw]


def _access(a: dict | None) -> DocumentAccess:
    # Unknown access is stored as an empty list: nobody matches it (fail closed).
    a = a or {}
    return DocumentAccess.build(
        user_emails=a.get("user_emails", []),
        user_groups=a.get("user_groups", []),
        external_user_emails=a.get("external_user_emails", []),
        external_user_group_ids=a.get("external_user_group_ids", []),
        is_public=a.get("is_public", False),
    )


def _chunk(d: dict) -> DocMetadataAwareIndexChunk:
    doc = Document(
        id=d["doc_id"],
        sections=[TextSection(text=d["text"], link=f"https://example.com/{d['doc_id']}")],
        source=DocumentSource.FILE,
        semantic_identifier=d["title"],
        metadata={},
    )
    return DocMetadataAwareIndexChunk(
        chunk_id=0,
        blurb=d["text"][:80],
        content=d["text"],
        source_links={0: f"https://example.com/{d['doc_id']}"},
        image_file_id=None,
        section_continuation=False,
        source_document=doc,
        title_prefix="",
        metadata_suffix_semantic="",
        metadata_suffix_keyword="",
        mini_chunk_texts=None,
        large_chunk_id=None,
        doc_summary="",
        chunk_context="",
        contextual_rag_reserved_tokens=0,
        embeddings=ChunkEmbedding(full_embedding=_vector(d["text"]), mini_chunk_embeddings=[]),
        tenant_id=TENANT,
        access=_access(d["access"]),
        document_sets=set(),
        user_project=[],
        personas=[],
        boost=0,
        aggregated_chunk_boost_factor=1.0,
        ancestor_hierarchy_node_ids=[],
    )


def _viewer(name: str) -> Viewer:
    v = TEST_SET["viewers"][name]
    return Viewer(email=v["email"], groups=frozenset(v.get("groups", [])), is_admin=v.get("is_admin", False))


def _source_docs() -> list[SourceDocument]:
    return [
        SourceDocument(doc_id=d["doc_id"], title=d["title"], access=_access(d["access"]) if d["access"] else None)
        for d in TEST_SET["documents"]
    ]


@pytest.fixture(scope="module")
def index():  # type: ignore[no-untyped-def]
    name = f"evolvxsi_acl_test_{uuid.uuid4().hex[:8]}"
    idx = OpenSearchDocumentIndex(
        tenant_state=TenantState(tenant_id=TENANT, multitenant=False),
        index_name=name,
        embedding_dim=DIM,
        vector_quantization=VectorQuantization.NONE,
    )
    idx.verify_and_create_index_if_necessary(embedding_dim=DIM)
    docs = TEST_SET["documents"]
    idx.index(
        [_chunk(d) for d in docs],
        IndexingMetadata(
            doc_id_to_chunk_cnt_diff={
                d["doc_id"]: IndexingMetadata.ChunkCounts(old_chunk_cnt=0, new_chunk_cnt=1) for d in docs
            }
        ),
    )
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = os.environ.get("OPENSEARCH_REST_API_PORT", "9200")
    requests.post(f"http://{host}:{port}/{name}/_refresh", timeout=10)
    yield idx
    requests.delete(f"http://{host}:{port}/{name}", timeout=10)


def _filters(viewer: Viewer) -> IndexFilters:
    return IndexFilters(access_control_list=sorted(viewer_acl(viewer)), tenant_id=TENANT)


def _expected_ids(viewer: Viewer) -> set[str]:
    # The index has no notion of the admin role, so unknown access is hidden
    # from everyone there. Compare against the rule with that in mind.
    return {
        d.doc_id for d in _source_docs() if d.access is not None and may_see(viewer, d)
    }


@pytest.mark.parametrize("viewer_name", sorted(TEST_SET["viewers"]))
def test_semantic_retrieval_returns_exactly_what_the_viewer_may_see(index, viewer_name: str) -> None:  # type: ignore[no-untyped-def]
    viewer = _viewer(viewer_name)
    chunks = index.semantic_retrieval(
        query_embedding=_vector("anything"), filters=_filters(viewer), num_to_retrieve=50
    )
    assert {c.document_id for c in chunks} == _expected_ids(viewer)


@pytest.mark.parametrize("viewer_name", sorted(TEST_SET["viewers"]))
@pytest.mark.parametrize("query,doc_id", [("receipts", "policy-travel-v2"), ("board ceiling", "board-acquisition-memo"), ("office open", "handbook-public"), ("payment terms", "unsynced-contract")])
def test_keyword_retrieval_never_returns_a_hidden_document(index, viewer_name: str, query: str, doc_id: str) -> None:  # type: ignore[no-untyped-def]
    viewer = _viewer(viewer_name)
    found = {c.document_id for c in index.keyword_retrieval(query=query, filters=_filters(viewer), num_to_retrieve=50)}
    assert found <= _expected_ids(viewer)
    if doc_id in _expected_ids(viewer):
        assert doc_id in found


def test_unknown_access_is_hidden_from_everyone_in_the_index(index) -> None:  # type: ignore[no-untyped-def]
    for name in TEST_SET["viewers"]:
        chunks = index.keyword_retrieval(query="payment terms", filters=_filters(_viewer(name)), num_to_retrieve=50)
        assert "unsynced-contract" not in {c.document_id for c in chunks}
