"""Drive pilot disclosure checks with real library and document records."""

from contextlib import nullcontext
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import Response

from nortpole.chat import history_access, search_evidence, selected_sources
from nortpole.configs.constants import DocumentSource, MessageType
from nortpole.context.search.models import (
    BaseFilters,
    CCPairAccessMode,
    PersonaSearchInfo,
    UserAccessFilters,
)
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import AccessType
from nortpole.db.models import ChatMessage, DocumentSet, DocumentSet__ConnectorCredentialPair, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.features.search import drive_pilot, workspace
from nortpole.server.query_and_chat.models import SearchEvidenceSelection
from shared_configs.contextvars import get_current_tenant_id
from tests.nortpole_integration.test_group_access import _doc, _source, _up
from tests.unit.nortpole.server.features.search.test_workspace_search import _chunk

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres and OpenSearch")


def test_drive_revocation_withholds_stale_search_and_chat_passages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tag = uuid4().hex
    identifier = f"pilot-{tag}"
    doc_id = f"https://docs.google.com/document/d/{identifier}"
    with get_session_with_current_tenant() as db:
        reader = User(
            email=f"drive-reader-{tag}@example.com",
            hashed_password="x",
            is_verified=True,
        )
        outsider = User(
            email=f"drive-other-{tag}@example.com",
            hashed_password="x",
            is_verified=True,
        )
        library = DocumentSet(name=f"drive-pilot-{tag}", is_public=True)
        other_library = DocumentSet(name=f"other-{tag}", is_public=True)
        db.add_all([reader, outsider, library, other_library])
        connector, credential, pair = _source(db, tag, AccessType.SYNC)
        connector.source = DocumentSource.GOOGLE_DRIVE
        credential.source = DocumentSource.GOOGLE_DRIVE
        db.add_all([
            DocumentSet__ConnectorCredentialPair(
                document_set_id=collection.id,
                connector_credential_pair_id=pair.id,
                is_current=True,
            )
            for collection in (library, other_library)
        ])
        _doc(db, doc_id, connector, credential)
        local_connector, local_credential, local_pair = _source(db, f"local-{tag}", AccessType.PUBLIC)
        db.add(DocumentSet__ConnectorCredentialPair(
            document_set_id=library.id, connector_credential_pair_id=local_pair.id, is_current=True,
        ))
        local_id = f"local-{tag}"
        _doc(db, local_id, local_connector, local_credential)
        db.flush()
        monkeypatch.setenv("NORTPOLE_SEARCH_DRIVE_PILOT_LIBRARY_ID", str(library.id))
        monkeypatch.setenv(
            "NORTPOLE_SEARCH_DRIVE_PILOT_TENANT", get_current_tenant_id()
        )
        enforced = CCPairAccessMode.ENFORCE
        monkeypatch.setattr(drive_pilot, "get_cc_pair_access_mode", lambda _: enforced)
        source = MagicMock()
        allowed = {reader.email}
        source.confirm_named_file_access.side_effect = lambda **opts: (
            opts["file_id"] == identifier and opts["viewer_email"] in allowed
        )
        monkeypatch.setattr(
            drive_pilot, "build_db_credentials_provider", lambda *_: None
        )
        monkeypatch.setattr(
            drive_pilot, "GoogleDriveSourceOperations", lambda **_: source
        )

        chunk = _chunk(1).model_copy(
            update={
                "document_id": doc_id,
                "source_type": DocumentSource.GOOGLE_DRIVE,
                "source_links": {0: "https://example.invalid/stale-index-link"},
            }
        )
        local_chunk = _chunk(2).model_copy(update={"document_id": local_id, "source_type": DocumentSource.FILE})
        research_chunks = [chunk]
        index = MagicMock()
        index.id_based_retrieval.side_effect = lambda requests, _filters: [
            item for item in (chunk, local_chunk)
            if any(request.document_id == item.document_id for request in requests)
        ]
        for module in (workspace, search_evidence):
            monkeypatch.setattr(module, "get_forced_document_set_names", lambda _: None)
            monkeypatch.setattr(module, "get_current_search_settings", lambda _: None)
            monkeypatch.setattr(module, "get_default_document_index", lambda *_: index)
            monkeypatch.setattr(
                module,
                "build_access_filters_for_user",
                lambda *_: UserAccessFilters(
                    access_control_list=[], cc_pair_access=None
                ),
            )
        monkeypatch.setattr(workspace, "get_redis_client", MagicMock)
        monkeypatch.setattr(
            workspace, "workspace_candidates", lambda *_: ([chunk], False)
        )
        # Use the same transaction for the Search and Chat authorization checks.
        monkeypatch.setattr(
            search_evidence, "get_session_with_current_tenant", lambda: nullcontext(db)
        )
        monkeypatch.setattr(history_access, "get_default_document_index", lambda *_: index)
        monkeypatch.setattr(history_access, "get_current_search_settings", lambda _: None)
        monkeypatch.setattr(selected_sources, "get_session_with_current_tenant", lambda: nullcontext(db))
        monkeypatch.setattr(selected_sources, "get_current_search_settings", lambda _: object())
        monkeypatch.setattr(selected_sources, "get_default_document_index", lambda *_: index)
        monkeypatch.setattr(selected_sources.EmbeddingModel, "from_db_model", lambda **_: None)
        monkeypatch.setattr(selected_sources, "search_pipeline", lambda *_, **__: research_chunks)

        def search(user: User):
            return workspace.search_workspace_knowledge(
                workspace.WorkspaceSearchRequest(
                    query="test",
                    library_id=library.id,
                    source=DocumentSource.GOOGLE_DRIVE,
                ),
                Response(),
                user,
                db,
            ).results

        def evidence_for(user: User):
            selection = SearchEvidenceSelection(
                documents=[{"document_id": doc_id, "chunk_id": 0}]
            )
            scope = PersonaSearchInfo(
                document_set_names=[],
                search_start_date=None,
                attached_document_ids=[],
                hierarchy_node_ids=[],
            )
            return search_evidence.resolve_search_evidence(
                selection, "test", scope, user, len, 1000
            )

        def research_scope(library_name: str) -> PersonaSearchInfo:
            return PersonaSearchInfo(
                document_set_names=[library_name], search_start_date=None,
                attached_document_ids=[], hierarchy_node_ids=[],
            )

        def research(user: User, library_name: str = library.name):
            return selected_sources.retrieve_selected_knowledge(
                "test", BaseFilters(document_set=[library_name]), research_scope(library_name),
                user, len, 1000, allow_empty=True, indexed_only=True, recheck_drive=True,
            )

        assert drive_pilot.eligible_drive_library(reader, db) == library.id
        (result,) = search(reader)
        assert (
            result.url == f"https://drive.google.com/open?id={identifier}"
            and result.excerpt
        )
        assert search(outsider) == []
        evidence, incomplete = evidence_for(reader)
        assert evidence[0].source_document.link == result.url and not incomplete
        assert evidence_for(outsider) == ([], True)
        (passage,) = research(reader)
        assert passage.source_document is not None and passage.source_document.link == result.url
        assert research(outsider) == []
        assert research(reader, other_library.name) == []
        prior = ChatMessage(
            message_type=MessageType.ASSISTANT,
            search_evidence_provenance=search_evidence.SearchEvidenceProvenance(
                indexed_sources=[(doc_id, 0, DocumentSource.GOOGLE_DRIVE)],
                knowledge_libraries=[library.name],
            ).model_dump(mode="json"),
        )

        def follow_up() -> None:
            search_evidence.verify_search_evidence_history(
                [prior], research_scope(library.name), reader, db=db, recheck_drive=True,
            )

        follow_up()

        allowed.clear()
        assert search(reader) == []
        assert evidence_for(reader) == ([], True)
        assert research(reader) == []
        with pytest.raises(NortPoleError, match="Start a new chat") as denied:
            follow_up()
        assert denied.value.error_code == NortPoleErrorCode.INSUFFICIENT_PERMISSIONS
        assert index.id_based_retrieval.call_count >= 3

        source.confirm_named_file_access.side_effect = RuntimeError(
            "provider unavailable"
        )
        assert search(reader) == []
        research_chunks.append(local_chunk)
        assert [item.file_id for item in research(reader)] == [local_id]
        with pytest.raises(NortPoleError, match="Start a new chat"):
            follow_up()
        enforced = CCPairAccessMode.SHADOW
        assert drive_pilot.eligible_drive_library(reader, db) is None
        assert search(reader) == []
        assert [item.file_id for item in research(reader)] == [local_id]
