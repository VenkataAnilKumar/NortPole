from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from nortpole.chat import search_evidence
from nortpole.chat.citation_processor import CitationMode, DynamicCitationProcessor
from nortpole.chat.citation_utils import build_context_file_citation_mapping
from nortpole.context.search.models import (
    PersonaSearchInfo,
    SavedSearchDoc,
    UserAccessFilters,
)
from nortpole.db.chat import (
    create_search_doc_from_saved_search_doc,
    translate_db_search_doc_to_saved_search_doc,
)
from nortpole.server.query_and_chat.models import (
    SearchEvidenceSelection,
    SendMessageRequest,
)
from nortpole.server.query_and_chat.streaming_models import CitationInfo
from tests.unit.nortpole.server.features.search.test_workspace_search import _chunk


@pytest.fixture
def index(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    current = MagicMock()
    monkeypatch.setattr(
        search_evidence,
        "get_session_with_current_tenant",
        lambda: nullcontext(object()),
    )
    monkeypatch.setattr(search_evidence, "get_current_search_settings", lambda _: None)
    monkeypatch.setattr(
        search_evidence, "get_default_document_index", lambda *_: current
    )
    monkeypatch.setattr(
        search_evidence, "get_forced_document_set_names", lambda _: None
    )
    monkeypatch.setattr(
        search_evidence,
        "build_access_filters_for_user",
        lambda *_: UserAccessFilters(
            access_control_list=["public"], cc_pair_access=None
        ),
    )
    return current


def _resolve(selection: SearchEvidenceSelection):
    persona = PersonaSearchInfo(
        document_set_names=[],
        search_start_date=None,
        attached_document_ids=[],
        hierarchy_node_ids=[],
    )
    return search_evidence.resolve_search_evidence(
        selection, "What is the policy?", persona, MagicMock(), len, 500
    )


def test_resolves_selected_chunk_and_omits_revoked_document(
    index, monkeypatch: pytest.MonkeyPatch
) -> None:
    index.id_based_retrieval.return_value = [_chunk(1, 3), _chunk(2, 7), _chunk(1, 4)]
    monkeypatch.setattr(
        search_evidence,
        "authorized_workspace_destinations",
        lambda *_: {"doc-01": "https://example.com/one"},
    )
    selection = SearchEvidenceSelection(
        documents=[
            {"document_id": "doc-01", "chunk_id": 3},
            {"document_id": "doc-02", "chunk_id": 7},
        ]
    )
    evidence, incomplete = _resolve(selection)
    assert incomplete
    assert [item.file_id for item in evidence] == ["doc-01"]
    assert evidence[0].source_document.chunk_ind == 3
    saved = create_search_doc_from_saved_search_doc(
        SavedSearchDoc.from_search_doc(evidence[0].source_document)
    )
    saved.id = 1
    restored = translate_db_search_doc_to_saved_search_doc(saved)
    assert restored.selected_evidence
    assert restored.metadata == evidence[0].source_document.metadata

    assert evidence[0].source_document.link == "https://example.com/one"
    processor = DynamicCitationProcessor(citation_mode=CitationMode.HYPERLINK)
    processor.update_citation_mapping(build_context_file_citation_mapping(evidence, {}))
    packets = [
        *processor.process_token("The policy applies [[1]]."),
        *processor.process_token(None),
    ]
    assert any(isinstance(packet, CitationInfo) for packet in packets)
    assert "https://example.com/one" in "".join(
        packet for packet in packets if isinstance(packet, str)
    )
    assert [
        req.min_chunk_ind for req in index.id_based_retrieval.call_args.args[0]
    ] == [3, 7]

    monkeypatch.setattr(
        search_evidence, "authorized_workspace_destinations", lambda *_: {}
    )
    assert _resolve(selection) == ([], True)


def test_revalidates_library_membership_before_using_passages(
    index, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        search_evidence,
        "get_document_set_by_id_for_user",
        lambda *_, **__: SimpleNamespace(name="Finance"),
    )
    monkeypatch.setattr(
        search_evidence,
        "workspace_candidates",
        lambda *_: ([_chunk(1), _chunk(2)], False),
    )
    monkeypatch.setattr(
        search_evidence,
        "authorized_workspace_destinations",
        lambda *_: {"doc-01": None, "doc-02": None},
    )
    monkeypatch.setattr(
        search_evidence,
        "fetch_document_sets_for_documents",
        lambda *_: [("doc-01", ["Finance"]), ("doc-02", ["HR"])],
    )
    evidence, _ = _resolve(SearchEvidenceSelection(library_id=4))
    assert [item.file_id for item in evidence] == ["doc-01"]
    index.id_based_retrieval.assert_not_called()


def test_search_evidence_rejects_ambiguous_scope_and_deep_research() -> None:
    doc = {"document_id": "doc-01", "chunk_id": 0}
    with pytest.raises(ValidationError):
        SearchEvidenceSelection(documents=[doc], library_id=4)
    with pytest.raises(ValidationError):
        SendMessageRequest(
            message="Test", deep_research=True, search_evidence={"documents": [doc]}
        )


@pytest.mark.parametrize("change", ["source_access", "library_access", "revision", "legacy"])
def test_followup_checks_previous_evidence_even_without_emitted_citations(
    change: str, index: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nortpole.configs.constants import MessageType
    from nortpole.db.models import ChatMessage
    from nortpole.error_handling.error_codes import NortPoleErrorCode
    from nortpole.error_handling.exceptions import NortPoleError

    chunk = _chunk(1, 7)
    index.id_based_retrieval.return_value = [chunk]
    library = MagicMock(return_value=SimpleNamespace(name="Finance"))
    destinations = MagicMock(return_value={"doc-01": None})
    monkeypatch.setattr(search_evidence, "get_document_set_by_id_for_user", library)
    monkeypatch.setattr(search_evidence, "authorized_workspace_destinations", destinations)
    monkeypatch.setattr(search_evidence, "workspace_candidates", lambda *_: ([chunk], False))
    monkeypatch.setattr(
        search_evidence, "fetch_document_sets_for_documents",
        lambda *_: [("doc-01", ["Finance"])],
    )
    evidence, _ = _resolve(SearchEvidenceSelection(library_id=4))
    record = search_evidence.SearchEvidenceProvenance.capture(evidence, 4)
    previous = ChatMessage(
        message_type=MessageType.ASSISTANT,
        message="A prior answer that used a source without citing it.",
        search_evidence_provenance=record.model_dump(mode="json", exclude_none=True),
    )
    persona = PersonaSearchInfo(
        document_set_names=[], search_start_date=None,
        attached_document_ids=[], hierarchy_node_ids=[],
    )
    user = MagicMock()
    search_evidence.verify_search_evidence_history([previous], persona, user)
    assert index.id_based_retrieval.call_args.args[0][0].min_chunk_ind == 7

    if change == "library_access":
        library.return_value = None
    elif change == "source_access":
        destinations.return_value = {}
    elif change == "revision":
        index.id_based_retrieval.return_value = [
            chunk.model_copy(update={"content": "A different revision"})
        ]
    else:
        previous.search_evidence_provenance = None
        previous.search_docs = [create_search_doc_from_saved_search_doc(
            SavedSearchDoc.from_search_doc(evidence[0].source_document)
        )]
    with pytest.raises(NortPoleError, match="Start a new chat") as denied:
        search_evidence.verify_search_evidence_history([previous], persona, user)
    assert denied.value.error_code == NortPoleErrorCode.INSUFFICIENT_PERMISSIONS


@pytest.mark.parametrize("budget", [250, 4000])
def test_expanded_passage_replays_the_evidence_beyond_the_legacy_cutoff(
    index, monkeypatch: pytest.MonkeyPatch, budget: int,
) -> None:
    from nortpole.configs.constants import MessageType
    from nortpole.db.models import ChatMessage
    from nortpole.error_handling.exceptions import NortPoleError

    clause = "Recheck access at follow-up retrieval and resource open."
    content = "This introduction explains the project background. " * 40 + clause
    chunk = _chunk(1, 7).model_copy(update={"content": content})
    index.id_based_retrieval.return_value = [chunk]
    monkeypatch.setattr(
        search_evidence, "authorized_workspace_destinations", lambda *_: {"doc-01": None}
    )
    persona = PersonaSearchInfo(
        document_set_names=[], search_start_date=None,
        attached_document_ids=[], hierarchy_node_ids=[],
    )
    user = MagicMock()
    selection = SearchEvidenceSelection(documents=[{"document_id": "doc-01", "chunk_id": 7}])
    evidence, incomplete = search_evidence.resolve_search_evidence(
        selection, "When is access rechecked for retrieval or resource open?", persona,
        user, len, budget, expand_passages=True,
    )
    assert not incomplete
    assert evidence[0].file_content == (content if budget == 4000 else clause)

    record = search_evidence.SearchEvidenceProvenance.capture(evidence, None)
    previous = ChatMessage(
        message_type=MessageType.ASSISTANT,
        search_evidence_provenance=record.model_dump(mode="json"),
    )
    search_evidence.verify_search_evidence_history([previous], persona, user)
    index.id_based_retrieval.return_value = [chunk.model_copy(update={
        "content": content.replace("Recheck", "Suspend"),
    })]
    with pytest.raises(NortPoleError, match="Start a new chat"):
        search_evidence.verify_search_evidence_history([previous], persona, user)


@pytest.mark.parametrize("temporary", [False, True])
def test_removed_implicit_file_blocks_the_selected_branch(
    temporary: bool,
) -> None:
    from uuid import uuid4

    from nortpole.configs.constants import MessageType
    from nortpole.db.models import ChatMessage
    from nortpole.error_handling.exceptions import NortPoleError

    file_id = uuid4()
    proof = search_evidence.SearchEvidenceProvenance(
        context_files={file_id: "stored-file"}
    ).model_dump(mode="json")
    history = [
        ChatMessage(
            id=4,
            message_type=MessageType.ASSISTANT,
            search_evidence_provenance=None if temporary else proof,
        )
    ]
    persona = PersonaSearchInfo(
        document_set_names=[], search_start_date=None,
        attached_document_ids=[], hierarchy_node_ids=[],
    )
    search_evidence.verify_search_evidence_history(
        history, persona, MagicMock(),
        context_files={file_id: "stored-file"}, temporary={"4": proof} if temporary else None,
    )
    with pytest.raises(NortPoleError, match="Start a new chat"):
        search_evidence.verify_search_evidence_history(
            history, persona, MagicMock(),
            context_files={file_id: "replacement-file"}, temporary={"4": proof} if temporary else None,
        )


@pytest.mark.parametrize("revoked", ["source", "attachment", "library_membership"])
def test_history_rechecks_uncited_indexed_evidence(
    revoked: str, index: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nortpole.chat import history_access
    from nortpole.configs.constants import DocumentSource, MessageType
    from nortpole.db.models import ChatMessage
    from nortpole.error_handling.exceptions import NortPoleError

    chunk = _chunk(1, 7)
    index.id_based_retrieval.return_value = [chunk]
    destinations = MagicMock(return_value={"doc-01": None})
    monkeypatch.setattr(history_access, "get_default_document_index", lambda *_: index)
    monkeypatch.setattr(history_access, "get_current_search_settings", lambda *_: None)
    monkeypatch.setattr(history_access, "censor_chunks_for_user", lambda chunks, _: chunks)
    monkeypatch.setattr(history_access, "authorized_workspace_destinations", destinations)
    membership = MagicMock(return_value=[("doc-01", ["Finance"])])
    monkeypatch.setattr(history_access, "fetch_document_sets_for_documents", membership)
    monkeypatch.setattr(history_access, "filter_document_set_names_by_user_access", lambda _, names, __: names)
    monkeypatch.setattr(
        history_access, "build_access_filters_for_user",
        lambda *_: UserAccessFilters(access_control_list=["public"], cc_pair_access=None),
    )
    previous = ChatMessage(
        id=4,
        message_type=MessageType.ASSISTANT,
        search_evidence_provenance=search_evidence.SearchEvidenceProvenance(
            indexed_sources=[("doc-01", 7, DocumentSource.FILE)]
        ).model_dump(mode="json"),
    )
    persona = PersonaSearchInfo(
        document_set_names=["Finance"] if revoked == "library_membership" else [],
        search_start_date=None,
        attached_document_ids=["doc-01"] if revoked == "attachment" else [],
        hierarchy_node_ids=[],
    )
    search_evidence.verify_search_evidence_history([previous], persona, MagicMock(), db=MagicMock())
    assert index.id_based_retrieval.call_args.args[1].attached_document_ids is None
    if revoked == "source":
        destinations.return_value = {}
    elif revoked == "attachment":
        persona.attached_document_ids = ["different-doc"]
    else:
        membership.return_value = [("doc-01", [])]
    with pytest.raises(NortPoleError, match="Start a new chat"):
        search_evidence.verify_search_evidence_history([previous], persona, MagicMock(), db=MagicMock())
