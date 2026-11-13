"""The tool catalog on the real database: what the admin view lists, what a chat keeps, and the audit."""

import uuid

import pytest
from sqlalchemy import text

from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.models import MCPServer, Tool, User
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.tool_catalog import api as cat_api
from evolvxsi.tool_catalog import catalog
from tests.evolvxsi_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]


class _T:
    def __init__(self, tool_id, cls_name):  # type: ignore[no-untyped-def]
        self.id, self.name = tool_id, cls_name
        self.__class__ = type(cls_name, (_T,), {})


@pytest.fixture()
def world():  # type: ignore[no-untyped-def]
    saved = catalog.load()
    catalog.save(catalog.CatalogPolicy(version=saved.version))
    with get_session_with_current_tenant() as s:
        server = MCPServer(owner="test", name=f"mcp-{TAG}", server_url=f"https://tools-{TAG}.example.com/mcp?token=secret-{TAG}")
        s.add(server)
        s.flush()
        tool = Tool(name=f"mcp_tool_{TAG}", description="test", mcp_server_id=server.id, enabled=True)
        s.add(tool)
        admin = User(id=uuid.uuid4(), email=f"cat-admin-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add(admin)
        s.commit()
        ids = {"server": server.id, "tool": tool.id, "admin": admin.id}
    yield ids
    catalog.save(saved)
    with get_session_with_current_tenant() as s:
        s.query(Tool).filter_by(id=ids["tool"]).delete()
        s.query(MCPServer).filter_by(id=ids["server"]).delete()
        s.execute(text("delete from evolvxsi_audit_event where actor_email = :e and row_hash is null"), {"e": f"cat-admin-{TAG}@example.com"})
        s.query(User).filter_by(id=ids["admin"]).delete()
        s.commit()


def test_the_admin_view_lists_every_tool_with_its_kind_and_no_secret(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        view = cat_api.get_catalog(_=None, db_session=s)
        by_id = {t.id: t for t in view.tools}
        mine = by_id[world["tool"]]
        assert (mine.kind, mine.source, mine.allowed, mine.host) == ("outside", "MCP", False, f"tools-{TAG}.example.com")
        assert f"secret-{TAG}" not in view.model_dump_json(), "only the host of an MCP server is shown"
        search = next(t for t in view.tools if t.name in ("internal_search", "Internal Search") or (t.kind == "read" and t.source == "built-in"))
        assert search.allowed
        assert {k.kind: k.on for k in view.kinds} == catalog.DEFAULTS


def test_a_chat_loses_an_outside_tool_until_it_is_turned_on(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        search_id = s.execute(text("select id from tool where in_code_tool_id='SearchTool' limit 1")).scalar()
        python_id = s.execute(text("select id from tool where in_code_tool_id='PythonTool' limit 1")).scalar()
        tools = {search_id: [_T(search_id, "SearchTool")], python_id: [_T(python_id, "PythonTool")], world["tool"]: [_T(world["tool"], "MCPTool")]}
        assert sorted(catalog.filter_tools(tools, s)) == [search_id]
        admin = s.get(User, world["admin"])
        cat_api.put_catalog(cat_api.CatalogUpdate(kinds={}, tools={str(world["tool"]): True}), user=admin, db_session=s)
        assert sorted(catalog.filter_tools(tools, s)) == sorted([search_id, world["tool"]])
        n = s.execute(text("select count(*) from evolvxsi_audit_event where resource_type='tool_catalog' and actor_email=:e and summary like :p"),
                      {"e": admin.email, "p": f"%tool {world['tool']} on%"}).scalar()
        assert n == 1


def test_unknown_kinds_and_tools_are_refused(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        admin = s.get(User, world["admin"])
        with pytest.raises(EvolvXSIError):
            cat_api.put_catalog(cat_api.CatalogUpdate(kinds={"everything": True}), user=admin, db_session=s)
        with pytest.raises(EvolvXSIError):
            cat_api.put_catalog(cat_api.CatalogUpdate(kinds={}, tools={"999999999": True}), user=admin, db_session=s)
        assert catalog.load().kinds == catalog.DEFAULTS
