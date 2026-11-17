"""Installed integrations as chat tools on the real database (decision 0008): who gets which tool, and what a call returns."""

import json
import uuid

import pytest
from sqlalchemy import select

from nortpole.agents.tools import ToolInvocation
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.governance.route_policy.audit import NortPoleAuditEvent
from nortpole.knowledge.source_requests.models import NortPoleSourceRequest
from nortpole.llm.cancellation import CancellationSignal
from nortpole.tools.models import ToolContext
from nortpole.work.integrations import policy, registry, secrets, service
from nortpole.work.integrations.chat_tools import chat_tools_for
from nortpole.work.integrations.models import NortPoleIntegrationUse
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]
SECRET = f"tok-CHAT-{TAG}"


@pytest.fixture()
def world(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv(secrets.ENV, secrets.generate_key())
    registry.reload()
    saved = policy.load()
    policy.save(policy.PolicyConfig())
    with get_session_with_current_tenant() as s:
        ann = User(id=uuid.uuid4(), email=f"chat-ann-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add(ann)
        s.commit()
        uid = ann.id
    yield uid
    policy.save(saved)
    with get_session_with_current_tenant() as s:
        s.query(NortPoleIntegrationUse).filter_by(user_id=uid).delete()
        s.query(NortPoleSourceRequest).filter_by(requested_by_id=uid).delete()
        s.query(User).filter_by(id=uid).delete()
        s.commit()


def fake(body, status=200):  # type: ignore[no-untyped-def]
    seen = []

    def transport(request):  # type: ignore[no-untyped-def]
        seen.append(request)
        return status, json.dumps(body).encode(), "application/json"

    transport.seen = seen  # type: ignore[attr-defined]
    return transport


def names(tools) -> set[str]:  # type: ignore[no-untyped-def]
    return {t.name for t in tools}


def invoke(tool, arguments):  # type: ignore[no-untyped-def]
    return tool.run(ToolInvocation(call_id="c1", arguments=arguments, cancellation=CancellationSignal(), update=lambda p: None), ToolContext())


def tools_for(uid, transport=None):  # type: ignore[no-untyped-def]
    """Build the person's tools with no database session left open, as chat does: a tool opens its own."""
    with get_session_with_current_tenant() as s:
        ann = s.get(User, uid)
        s.expunge(ann)
    return chat_tools_for(ann, transport=transport)


def approve_and_install(s, ann, integration_id: str) -> None:  # type: ignore[no-untyped-def]
    s.add(NortPoleSourceRequest(kind="plugin", item_key=f"integration:{integration_id}", item_name=integration_id, reason="", state="approved", requested_by_id=ann.id, requested_by_email=ann.email))
    s.commit()
    service.install(s, ann, integration_id)


def test_nothing_is_offered_until_a_person_installs_and_connects(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world)
        assert chat_tools_for(ann) == []
        service.install(s, ann, "wikipedia")
        approve_and_install(s, ann, "airtable")
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world)
        got = names(chat_tools_for(ann))
        assert got == {"wikipedia_page_summary", "wikipedia_search"}, "airtable needs an account and none is connected"
        service.connect(s, ann, "airtable", {"access_token": SECRET})
        got = names(chat_tools_for(ann))
        assert {"airtable_list_bases", "airtable_list_tables", "airtable_list_records", "airtable_get_record"} <= got


def test_writes_are_never_offered_to_the_model(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world)
        approve_and_install(s, ann, "airtable")
        service.connect(s, ann, "airtable", {"access_token": SECRET})
        got = names(chat_tools_for(ann))
        for write in ("airtable_create_record", "airtable_update_record", "airtable_delete_record"):
            assert write not in got
        assert not any(t.name.endswith(("create_record", "update_record", "delete_record")) for t in chat_tools_for(ann))


def test_a_blocked_integration_or_a_removed_one_disappears_and_a_taken_name_is_skipped(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world)
        service.install(s, ann, "wikipedia")
        assert "wikipedia_search" in names(chat_tools_for(ann))
        assert "wikipedia_search" not in names(chat_tools_for(ann, {"wikipedia_search"})), "a built-in tool with that name wins"
        policy.save(policy.PolicyConfig(integrations={"wikipedia": "blocked"}))
        assert chat_tools_for(ann) == []
        policy.save(policy.PolicyConfig())
        service.remove(s, ann, "wikipedia")
        assert chat_tools_for(ann) == []


def test_a_call_runs_as_the_person_returns_the_result_and_is_audited(world) -> None:  # type: ignore[no-untyped-def]
    transport = fake({"query": {"search": [{"title": "North Pole"}]}})
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world)
        service.install(s, ann, "wikipedia", {"limit": 3})
    tool = next(t for t in tools_for(world, transport) if t.name == "wikipedia_search")
    assert set(tool.tool_definition().parameters["properties"]) == {"query"}
    result = invoke(tool, {"query": "north pole"})
    assert not result.is_error and "North Pole" in result.content
    assert transport.seen[0].query["srlimit"] == "3", "the person's own setting still applies"  # type: ignore[attr-defined]
    with get_session_with_current_tenant() as s:
        rows = [r for r in s.scalars(select(NortPoleAuditEvent).where(NortPoleAuditEvent.action == "tool.call")).all()
                if str(world) in json.dumps(r.details or {}) and "wikipedia" in json.dumps(r.details or {})]
        assert rows, "the call is audited like any other integration call"
        assert all("north pole" not in json.dumps(r.details or {}).lower() for r in rows), "the audit row never holds what was asked"


def test_a_refused_call_comes_back_as_a_safe_message_for_the_model_and_the_secret_never_appears(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world)
        approve_and_install(s, ann, "airtable")
        service.connect(s, ann, "airtable", {"access_token": SECRET})
    tools = tools_for(world, fake({"records": []}))
    lister = next(t for t in tools if t.name == "airtable_list_records")
    missing = invoke(lister, {"tableId": "tblX"})  # the base is required
    assert missing.is_error and "baseId" in missing.content and SECRET not in missing.content
    ok = invoke(lister, {"baseId": "appX", "tableId": "tblX"})
    assert not ok.is_error and SECRET not in ok.content
    for t in tools:
        assert SECRET not in json.dumps(t.tool_definition().model_dump()) and SECRET not in t.description
    policy.save(policy.PolicyConfig(integrations={"airtable": "blocked"}))
    blocked = invoke(lister, {"baseId": "appX", "tableId": "tblX"})
    assert blocked.is_error and "blocked" in blocked.content, "a policy change after the tool was built still stops the call"
    policy.save(policy.PolicyConfig())


def test_a_big_result_is_cut_and_says_so(world) -> None:  # type: ignore[no-untyped-def]
    big = fake({"query": {"search": [{"title": "x" * 100} for _ in range(1000)]}})
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world)
        service.install(s, ann, "wikipedia")
    tool = next(t for t in tools_for(world, big) if t.name == "wikipedia_search")
    out = invoke(tool, {"query": "x"})
    assert len(out.content) < 21_000 and "truncated" in out.content
