from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from nortpole.configs.constants import DocumentSource
from nortpole.context.search.models import InferenceChunk, UserAccessFilters
from nortpole.db.models import User
from nortpole.server.features.search import workspace
from nortpole.tracing.framework import set_trace_processors
from tests.unit.nortpole.tracing.capture import CaptureProcessor


def _chunk(number: int, chunk_id: int = 0) -> InferenceChunk:
    return InferenceChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{number:02}",
        title=f"Policy {number}",
        semantic_identifier=f"Policy {number}",
        source_type=DocumentSource.FILE,
        boost=0,
        score=1,
        hidden=False,
        metadata={},
        match_highlights=[],
        doc_summary="",
        chunk_context="",
        updated_at=None,
        blurb="",
        content="Private test excerpt",
        source_links=None,
        image_file_id=None,
        section_continuation=False,
    )


def test_workspace_search_groups_pages_and_rechecks_acl_without_chat_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Index:
        def keyword_retrieval(self, _query, _filters, _size):
            return [_chunk(n, chunk) for n in reversed(range(45)) for chunk in (1, 0)]

    class Redis:
        def __init__(self):
            self.values = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value, *, ex):
            assert ex == workspace.CURSOR_TTL_SECONDS
            self.values[key] = value

    def offline(*_args, **_kwargs):
        raise RuntimeError("test query data must stay out of telemetry")

    user = User(id=uuid4())
    db = object()
    store = Redis()
    revoked = set()
    monkeypatch.setattr(workspace, "get_redis_client", lambda: store)
    monkeypatch.setattr(workspace, "get_forced_document_set_names", lambda _: None)
    monkeypatch.setattr(workspace, "get_current_search_settings", lambda _: None)
    monkeypatch.setattr(workspace, "get_default_document_index", lambda *_: Index())
    monkeypatch.setattr(workspace, "get_query_embedding", offline)
    monkeypatch.setattr(
        workspace,
        "build_access_filters_for_user",
        lambda *_: UserAccessFilters(
            access_control_list=["public"], cc_pair_access=None
        ),
    )
    monkeypatch.setattr(
        workspace,
        "authorized_workspace_destinations",
        lambda ranked, *_: {key: None for key in ranked if key not in revoked},
    )
    capture = CaptureProcessor()
    set_trace_processors([capture])

    def search(cursor=None, principal=user):
        response = Response()
        result = workspace.search_workspace_knowledge(
            workspace.WorkspaceSearchRequest(query="Private test query", cursor=cursor),
            response,
            principal,
            db,
        )
        assert response.headers["Cache-Control"] == "private, no-store"
        assert result.lexical_only
        return result

    try:
        first = search()
        assert first.next_cursor is not None
        with pytest.raises(HTTPException) as borrowed:
            search(first.next_cursor, User(id=uuid4()))
        assert borrowed.value.status_code == 410
        revoked.add("doc-21")
        second = search(first.next_cursor)
        assert second.next_cursor is not None
        third = search(second.next_cursor)
        assert third.next_cursor is None
    finally:
        set_trace_processors([])

    ids = [item.id for page in (first, second, third) for item in page.results]
    assert ids == [f"doc-{n:02}" for n in range(45) if n != 21]
    assert not capture.started_traces and not capture.ended_spans
    assert all("Private test" not in value for value in store.values.values())


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "//host.test",
        "https://user@host.test",
        "https://a\\b.test",
    ],
)
def test_workspace_disallows_unsafe_original_links(url: str) -> None:
    assert workspace._external_url(url) is None
