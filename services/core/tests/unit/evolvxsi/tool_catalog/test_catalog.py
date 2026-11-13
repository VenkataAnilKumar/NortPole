"""The tool catalog: kinds, defaults, per-tool overrides, and failing closed."""

from types import SimpleNamespace

from evolvxsi.tool_catalog import catalog
from evolvxsi.tool_catalog.catalog import CatalogPolicy, filter_tools, kind_of_row


class Fake:
    def __init__(self, tool_id, cls_name="X", name=None):  # type: ignore[no-untyped-def]
        self.id, self.name = tool_id, name or cls_name
        self.__class__ = type(cls_name, (Fake,), {})


class DB:
    """Answers the row query with fixed rows; or raises, to test failing closed."""

    def __init__(self, rows=None, fail=False):  # type: ignore[no-untyped-def]
        self.rows, self.fail = rows or [], fail

    def query(self, *a):  # type: ignore[no-untyped-def]
        if self.fail:
            raise RuntimeError("database down")
        rows = self.rows

        class Q:
            def filter(self, *a):  # type: ignore[no-untyped-def]
                return rows
        return Q()


def _row(i, code=None, mcp=None, api=None):  # type: ignore[no-untyped-def]
    return SimpleNamespace(id=i, in_code_tool_id=code, mcp_server_id=mcp, openapi_schema=api)


def test_kinds_of_the_core_tools() -> None:
    assert kind_of_row("SearchTool", None, None) == "read"
    assert kind_of_row("OpenURLTool", None, None) == "web"
    assert kind_of_row("PythonTool", None, None) == "code" and kind_of_row("CodingAgentTool", None, None) == "code"
    assert kind_of_row(None, 3, None) == "outside" and kind_of_row(None, None, {"openapi": "3"}) == "outside"
    assert kind_of_row("SomethingNew", None, None) == "outside", "a tool the catalog does not know counts as outside"
    assert kind_of_row("SearchTool", 3, None) == "outside", "an MCP tool cannot pass as a built-in by its id"


def test_defaults_keep_code_and_outside_tools_off() -> None:
    p = CatalogPolicy()
    assert [k for k in catalog.KINDS if p.kind_on(k)] == ["read", "web", "generate", "personal"]
    assert not catalog.code_allowed(p)


def test_a_per_tool_setting_overrides_its_kind() -> None:
    p = CatalogPolicy(tools={"7": False, "20": True})
    assert not p.allows(7, "web") and p.allows(20, "outside") and p.allows(1, "read") and not p.allows(21, "outside")


def test_filter_keeps_allowed_tools_and_drops_the_rest() -> None:
    db = DB([_row(1, "SearchTool"), _row(6, "PythonTool"), _row(20, None, mcp=3), _row(7, "OpenURLTool")])
    tools = {1: [Fake(1, "SearchTool")], 6: [Fake(6, "PythonTool")], 20: [Fake(20, "MCPTool")], 7: [Fake(7, "OpenURLTool")]}
    out = filter_tools(tools, db, CatalogPolicy())
    assert sorted(out) == [1, 7]
    out = filter_tools(tools, db, CatalogPolicy(tools={"20": True}, kinds={**catalog.DEFAULTS, "web": False}))
    assert sorted(out) == [1, 20]


def test_a_tool_with_no_database_row_is_judged_by_its_class() -> None:
    tools = {-1: [Fake(None, "SearchTool")], -2: [Fake(None, "UnknownTool")]}
    out = filter_tools(tools, DB([]), CatalogPolicy())
    assert sorted(out) == [-1]


def test_if_the_check_fails_only_read_tools_stay() -> None:
    tools = {1: [Fake(1, "SearchTool")], 7: [Fake(7, "OpenURLTool")], 6: [Fake(6, "PythonTool")]}
    out = filter_tools(tools, DB(fail=True), CatalogPolicy(kinds={k: True for k in catalog.KINDS}))
    assert sorted(out) == [1], "a broken check must not let more through"
