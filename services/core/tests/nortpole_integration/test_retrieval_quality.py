"""Search quality with a real embedding model, plus access, on a real index (A5).

Embeds a synthetic policy corpus with `nomic-embed-text` (served by Ollama),
indexes it in OpenSearch with the core's own index code, and measures how often
the expected document is found for a reworded question, for meaning-based
(semantic) and keyword search. The board memo is restricted: it must never be
returned to a viewer without access, however well it matches.

Skips unless OpenSearch and Ollama (127.0.0.1:11434) are running. Thresholds are
deliberately modest: they catch a broken pipeline, not fine ranking differences.
"""

import json
import os
import uuid
from pathlib import Path

import pytest
import requests

from nortpole.access.models import DocumentAccess
from nortpole.context.search.models import IndexFilters
from nortpole.db.enums import VectorQuantization
from nortpole.document_index.interfaces import IndexingMetadata, TenantState
from nortpole.document_index.opensearch.opensearch_document_index import OpenSearchDocumentIndex
from nortpole.indexing.models import ChunkEmbedding
from nortpole.knowledge.knowledge_access.decisions import Viewer, viewer_acl
from tests.nortpole_integration.test_retrieval_acl import TENANT, _chunk, _opensearch_up

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = "nomic-embed-text"
DIM = 768
SET = json.loads((Path(__file__).parent / "retrieval_quality_set.json").read_text())


def _ollama_ready() -> bool:
    try:
        tags = requests.get(f"{OLLAMA}/api/tags", timeout=2).json()
        return any(m["name"].startswith(MODEL) for m in tags.get("models", []))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not (_opensearch_up() and _ollama_ready()), reason="needs OpenSearch and Ollama with nomic-embed-text")


def _embed(texts: list[str], kind: str) -> list[list[float]]:
    r = requests.post(f"{OLLAMA}/api/embed", json={"model": MODEL, "input": [f"{kind}: {t}" for t in texts]}, timeout=120)
    r.raise_for_status()
    return r.json()["embeddings"]


@pytest.fixture(scope="module")
def index():  # type: ignore[no-untyped-def]
    name = f"nortpole_quality_{uuid.uuid4().hex[:8]}"
    idx = OpenSearchDocumentIndex(TenantState(tenant_id=TENANT, multitenant=False), name, DIM, VectorQuantization.NONE)
    idx.verify_and_create_index_if_necessary(embedding_dim=DIM)
    docs = SET["documents"]
    vectors = _embed([d["text"] for d in docs], "search_document")
    chunks = []
    for d, v in zip(docs, vectors):
        restricted = d["doc_id"] in SET["restricted"]
        access = DocumentAccess.build(
            user_emails=["ceo@example.com"] if restricted else [], user_groups=["board"] if restricted else [],
            external_user_emails=[], external_user_group_ids=[], is_public=not restricted,
        )
        c = _chunk({"doc_id": d["doc_id"], "title": d["title"], "text": d["text"], "access": None})
        chunks.append(c.model_copy(update={"access": access, "embeddings": ChunkEmbedding(full_embedding=v, mini_chunk_embeddings=[])}))
    idx.index(chunks, IndexingMetadata(doc_id_to_chunk_cnt_diff={d["doc_id"]: IndexingMetadata.ChunkCounts(old_chunk_cnt=0, new_chunk_cnt=1) for d in docs}))
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    requests.post(f"http://{host}:9200/{name}/_refresh", timeout=10)
    yield idx
    requests.delete(f"http://{host}:9200/{name}", timeout=10)


def _filters(viewer: Viewer) -> IndexFilters:
    return IndexFilters(access_control_list=sorted(viewer_acl(viewer)), tenant_id=TENANT)


STAFF = Viewer(email="staff@example.com")
BOARD = Viewer(email="ceo@example.com", groups=frozenset({"board"}))


def _recall(idx, viewer: Viewer, mode: str, k: int) -> float:  # type: ignore[no-untyped-def]
    qs = SET["queries"]
    qv = _embed([q["q"] for q in qs], "search_query")
    hits = 0
    for q, v in zip(qs, qv):
        if mode == "semantic":
            found = idx.semantic_retrieval(query_embedding=v, filters=_filters(viewer), num_to_retrieve=k)
        else:
            found = idx.keyword_retrieval(query=q["q"], filters=_filters(viewer), num_to_retrieve=k)
        hits += q["expect"] in [c.document_id for c in found]
    return hits / len(qs)


def test_semantic_search_finds_the_right_document_for_reworded_questions(index) -> None:  # type: ignore[no-untyped-def]
    # The board question is unanswerable for staff, so measure staff on the rest.
    visible = [q for q in SET["queries"] if q["expect"] not in SET["restricted"]]
    qv = _embed([q["q"] for q in visible], "search_query")
    at1 = at3 = 0
    for q, v in zip(visible, qv):
        ids = [c.document_id for c in index.semantic_retrieval(query_embedding=v, filters=_filters(STAFF), num_to_retrieve=3)]
        at1 += bool(ids) and ids[0] == q["expect"]
        at3 += q["expect"] in ids
    n = len(visible)
    print(f"\nsemantic recall@1={at1/n:.2f} recall@3={at3/n:.2f} over {n} questions")
    assert at3 / n >= 0.85, "meaning-based search should find most reworded questions in the top 3"


def test_semantic_beats_keyword_on_reworded_questions(index) -> None:  # type: ignore[no-untyped-def]
    sem = _recall(index, BOARD, "semantic", 3)
    kw = _recall(index, BOARD, "keyword", 3)
    print(f"\nrecall@3 semantic={sem:.2f} keyword={kw:.2f} (board viewer, all {len(SET['queries'])} questions)")
    assert sem >= kw, "reworded questions are exactly where keyword matching falls behind"


def test_the_restricted_memo_is_never_returned_without_access(index) -> None:  # type: ignore[no-untyped-def]
    for q in SET["queries"]:
        v = _embed([q["q"]], "search_query")[0]
        for mode in ("semantic", "keyword"):
            found = (index.semantic_retrieval(query_embedding=v, filters=_filters(STAFF), num_to_retrieve=24)
                     if mode == "semantic" else index.keyword_retrieval(query=q["q"], filters=_filters(STAFF), num_to_retrieve=24))
            assert "board-acquisition" not in [c.document_id for c in found], (mode, q["q"])


def test_the_board_can_find_it_with_the_right_access(index) -> None:  # type: ignore[no-untyped-def]
    q = next(q for q in SET["queries"] if q["expect"] == "board-acquisition")
    v = _embed([q["q"]], "search_query")[0]
    ids = [c.document_id for c in index.semantic_retrieval(query_embedding=v, filters=_filters(BOARD), num_to_retrieve=3)]
    assert "board-acquisition" in ids


def test_the_task_evidence_step_uses_meaning_based_search_and_access(index) -> None:  # type: ignore[no-untyped-def]
    """`gather_evidence` end to end: the question is embedded with the configured
    model (here Ollama), a reworded question finds the right document that
    keyword matching would miss, and a restricted document stays hidden."""
    from unittest.mock import MagicMock, patch

    from nortpole.work.tasks import evidence

    def run(viewer: Viewer, question: str) -> list[str]:
        user = MagicMock()
        with patch.object(evidence, "DISABLE_VECTOR_DB", False), \
             patch("nortpole.db.search_settings.get_active_search_settings", return_value=MagicMock(primary=None, secondary=None)), \
             patch("nortpole.document_index.factory.get_default_document_index", return_value=index), \
             patch("nortpole.work.tasks.evidence.build_access_filters_for_user",
                   return_value=MagicMock(access_control_list=sorted(viewer_acl(viewer)), cc_pair_access=None)), \
             patch("nortpole.context.search.utils.get_query_embedding", side_effect=lambda q, db=None: _embed([q], "search_query")[0]):
            return [e.doc_id for e in evidence.gather_evidence(MagicMock(), user, question)]

    reworded = "Can a guest walk around the building alone?"
    assert "visitor-policy" in run(STAFF, reworded)
    board_q = "What is the price limit the board set for the takeover?"
    assert "board-acquisition" not in run(STAFF, board_q)
    assert "board-acquisition" in run(BOARD, board_q)
