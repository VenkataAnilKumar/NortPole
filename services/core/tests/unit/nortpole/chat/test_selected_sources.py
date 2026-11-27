from io import BytesIO
from unittest.mock import Mock

import pytest

from nortpole.chat import selected_sources
from nortpole.chat.citation_utils import build_context_file_citation_mapping
from nortpole.chat.evidence_relevance import comparison_topics
from nortpole.chat.prompt_utils import _create_context_files_message
from nortpole.configs.constants import DocumentSource
from nortpole.context.search.models import (
    BaseFilters,
    InferenceChunk,
    PersonaSearchInfo,
    SearchDoc,
)
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.file_store.models import (
    ChatFileInput,
    ChatFileType,
    ContextFileMetadata,
    ExtractedContextFiles,
)


def test_small_csv_uses_complete_attached_file_only(monkeypatch: pytest.MonkeyPatch) -> None:
    bytes_ = b'id,description,amount\nE1,"Hotel, room",120\nE2,Taxi,95\n'
    store = Mock()
    store.get_file_size.side_effect = lambda id_: (
        len(bytes_) if id_ == "current" else selected_sources.MAX_INLINE_CSV_BYTES + 1
    )
    store.read_file.return_value = BytesIO(bytes_)
    monkeypatch.setattr(selected_sources, "get_default_file_store", lambda: store)
    files = [
        ChatFileInput(
            descriptor={"id": id_, "type": ChatFileType.TABULAR, "name": f"{id_}.csv"},
            token_count=20,
            content_pending=False,
        )
        for id_ in ("prior", "current", "oversized")
    ]
    results = selected_sources.load_small_csv_sources(
        files, {"current", "oversized"}, len, 1000
    )
    assert [source.file_content for source in results] == [bytes_.decode().strip()]
    store.read_file.assert_called_once_with("current", mode="b")


def test_requested_library_cannot_escape_agent_scope() -> None:
    persona = PersonaSearchInfo(
        document_set_names=["Allowed"],
        search_start_date=None,
        attached_document_ids=[],
        hierarchy_node_ids=[],
    )
    with pytest.raises(NortPoleError, match="outside this agent's search scope"):
        selected_sources.retrieve_selected_knowledge(
            "query", BaseFilters(document_set=["Other"]), persona, Mock(), len, 1000
        )


def test_knowledge_context_preserves_real_document_citation() -> None:
    source = SearchDoc(
        document_id="policy",
        chunk_ind=0,
        semantic_identifier="Expense policy",
        link="https://example.invalid/policy",
        blurb="Expenses over $75 require a receipt.",
        source_type=DocumentSource.INGESTION_API,
        boost=1,
        hidden=False,
        metadata={},
        match_highlights=[],
    )
    metadata = ContextFileMetadata(
        file_id=source.document_id,
        filename=source.semantic_identifier,
        file_content=source.blurb,
        source_document=source,
    )
    assert build_context_file_citation_mapping([metadata], {}) == {1: source}
    context = ExtractedContextFiles(
        file_texts=[source.blurb],
        image_files=[],
        use_as_search_filter=False,
        total_token_count=10,
        file_metadata=[metadata],
        uncapped_token_count=10,
    )
    prompt = _create_context_files_message(context, {"policy": 4})
    assert '"citation": "[[4]]"' in prompt.content


def test_missing_csv_fails_before_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    store = Mock()
    store.get_file_size.side_effect = FileNotFoundError
    monkeypatch.setattr(selected_sources, "get_default_file_store", lambda: store)
    attachment = ChatFileInput(
        descriptor={"id": "current", "type": ChatFileType.TABULAR, "name": "missing.csv"},
        token_count=20,
        content_pending=False,
    )
    with pytest.raises(NortPoleError, match="missing.csv"):
        selected_sources.load_small_csv_sources([attachment], {"current"}, len, 1000)


def test_selected_knowledge_respects_disabled_sources() -> None:
    persona = PersonaSearchInfo(
        document_set_names=["Allowed"],
        search_start_date=None,
        attached_document_ids=[],
        hierarchy_node_ids=[],
    )
    with pytest.raises(NortPoleError, match="Enable a search source"):
        selected_sources.retrieve_selected_knowledge(
            "query",
            BaseFilters(document_set=["Allowed"], source_type=[]),
            persona,
            Mock(),
            len,
            1000,
        )


def test_indexed_knowledge_prioritizes_top_passages_from_distinct_documents() -> None:
    high_rank = Mock(spec=InferenceChunk, document_id="search")
    adjacent = Mock(spec=InferenceChunk, document_id="search")
    next_document = Mock(spec=InferenceChunk, document_id="chat")
    later_from_next = Mock(spec=InferenceChunk, document_id="chat")

    result = selected_sources._prioritize_distinct_documents(
        [high_rank, adjacent, next_document, later_from_next]
    )

    assert result == [high_rank, next_document, adjacent, later_from_next]


def test_comparison_passages_rank_for_each_topic_by_content() -> None:
    opening = Mock(spec=InferenceChunk, content="Overview of the Search and Chat comparison.")
    retrieval = Mock(spec=InferenceChunk, content="Recheck access at follow-up retrieval.")
    handoff = Mock(spec=InferenceChunk, content="If a source is revoked, use the remaining evidence.")
    question = (
        "Compare the Search plan and Chat handoff. When do they recheck access, "
        "and what happens after source revocation?"
    )
    topics = comparison_topics(question)
    assert len(topics) == 2
    assert selected_sources._rank_comparison_passages(
        topics, [[opening, retrieval], [opening, handoff]], question=question,
    ) == [retrieval, handoff, opening]
