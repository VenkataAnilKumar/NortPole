"""Discover and requests on the real database: what is offered, one waiting request per item, withdraw, the
administrator's decision, and what the audit records."""

import uuid

import pytest
from sqlalchemy import text

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import MCPServer, Notification, Tool, User
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.work.packs.models import NortPolePackVersion
from nortpole.knowledge.source_requests import api
from nortpole.knowledge.source_requests.models import NortPoleSourceRequest
from nortpole.governance.tool_catalog import api as cat_api
from nortpole.governance.tool_catalog import catalog as cat
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]
REASON = f"for the quarterly close {TAG}"


@pytest.fixture()
def world():  # type: ignore[no-untyped-def]
    saved = cat.load()
    cat.save(cat.CatalogPolicy(version=saved.version))
    with get_session_with_current_tenant() as s:
        people = [User(id=uuid.uuid4(), email=f"src-{n}-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True) for n in ("ann", "bob", "admin")]
        s.add_all(people)
        server = MCPServer(owner="test", name=f"src-mcp-{TAG}", server_url="https://tools.example.com/mcp")
        s.add(server)
        s.flush()
        tool = Tool(name=f"src_tool_{TAG}", description="test", mcp_server_id=server.id, enabled=True)
        pack = NortPolePackVersion(pack_id=f"src-pack-{TAG}", version="1.0.0", manifest={"name": f"Pack {TAG}", "description": "A test pack"},
                                   digest="0" * 64, signature="x", signer_key_id="test", active=False)
        s.add_all([tool, pack])
        s.commit()
        ids = {"ann": people[0].id, "bob": people[1].id, "admin": people[2].id, "tool": tool.id, "server": server.id}
    yield ids
    cat.save(saved)
    with get_session_with_current_tenant() as s:
        s.query(NortPoleSourceRequest).filter(NortPoleSourceRequest.requested_by_email.like(f"%-{TAG}@example.com")).delete(synchronize_session=False)
        s.query(NortPolePackVersion).filter_by(pack_id=f"src-pack-{TAG}").delete()
        s.query(Tool).filter_by(id=ids["tool"]).delete()
        s.query(MCPServer).filter_by(id=ids["server"]).delete()
        s.execute(text("delete from evolvxsi_audit_event where actor_email like :p and row_hash is null"), {"p": f"src-%-{TAG}@example.com"})
        s.query(Notification).filter(Notification.user_id.in_([ids["ann"], ids["bob"], ids["admin"]])).delete(synchronize_session=False)
        s.query(User).filter(User.id.in_([ids["ann"], ids["bob"], ids["admin"]])).delete(synchronize_session=False)
        s.commit()


def test_discover_offers_unconnected_types_inactive_packs_and_tools_that_are_not_allowed(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        view = api.get_discover(user=s.get(User, world["ann"]), db_session=s)
        keys = {(i.kind, i.key) for i in view.items}
        assert ("skill", f"src-pack-{TAG}") in keys
        assert ("plugin", str(world["tool"])) in keys, "an outside tool that is not approved is offered"
        assert any(k == "connector" for k, _ in keys)
        assert all(i.why_approval for i in view.items)
        allowed = {str(t.id) for t in cat_api.build(s).tools if t.allowed and t.core_enabled}
        assert allowed, "the default catalog allows the built-in read tools"
        assert not any(kind == "plugin" and key in allowed for kind, key in keys), "tools already allowed are not offered"


def test_one_waiting_request_per_item_then_withdraw_and_decide(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann, bob, admin = s.get(User, world["ann"]), s.get(User, world["bob"]), s.get(User, world["admin"])
        r = api.create_request(api.NewRequest(kind="skill", item_key=f"src-pack-{TAG}", reason=REASON), user=ann, db_session=s)
        assert (r.state, r.item_name, r.manage_at) == ("pending", f"Pack {TAG}", "/admin/packs")
        with pytest.raises(NortPoleError):
            api.create_request(api.NewRequest(kind="skill", item_key=f"src-pack-{TAG}"), user=ann, db_session=s)
        with pytest.raises(NortPoleError):
            api.create_request(api.NewRequest(kind="skill", item_key="no-such-pack"), user=ann, db_session=s)
        with pytest.raises(NortPoleError):
            api.create_request(api.NewRequest(kind="theme", item_key="x"), user=ann, db_session=s)
        mine = next(i for i in api.get_discover(user=ann, db_session=s).items if i.key == f"src-pack-{TAG}")
        assert mine.my_request is not None and mine.my_request.state == "pending"
        others = next(i for i in api.get_discover(user=bob, db_session=s).items if i.key == f"src-pack-{TAG}")
        assert others.my_request is None, "people see only their own requests"

        with pytest.raises(NortPoleError):
            api.withdraw_request(r.id, user=bob, db_session=s)
        assert api.withdraw_request(r.id, user=ann, db_session=s).state == "withdrawn"
        r2 = api.create_request(api.NewRequest(kind="plugin", item_key=str(world["tool"])), user=ann, db_session=s)
        assert any(p.id == r2.id for p in api.list_requests(_=admin, db_session=s).pending)
        decided = api.decide_request(r2.id, api.Decision(approve=True, note="Approving; will set it up"), user=admin, db_session=s)
        assert (decided.state, decided.decided_by_email, decided.manage_at) == ("approved", admin.email, "/admin/tool-catalog")
        with pytest.raises(NortPoleError):
            api.decide_request(r2.id, api.Decision(approve=False), user=admin, db_session=s)
        assert not cat.load().allows(world["tool"], "outside"), "approving a request turns nothing on"
        told = s.query(Notification).filter_by(user_id=ann.id).all()
        assert len(told) == 1 and told[0].notif_type.value == "source_request_decided"
        assert told[0].title == f"Your request for src_tool_{TAG} was approved" and "Approving; will set it up" in (told[0].description or "")
        assert not s.query(Notification).filter_by(user_id=bob.id).count(), "only the requester is told"

        rows = s.execute(text("select action, details::text from evolvxsi_audit_event where actor_email in (:a, :b) order by id"),
                         {"a": ann.email, "b": admin.email}).all()
        actions = [a for a, _ in rows]
        assert actions.count("source.request") == 3 and actions.count("source.request_decide") == 1
        assert all(REASON not in (d or "") for _, d in rows), "the person's reason is not copied into the audit log"
