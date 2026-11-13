"""Which tools chat agents may use. Every tool the core can give a chat agent is put in a kind, and each kind (and
each single tool) is on or off. The check runs where the core builds a chat's tools, so a tool that is off is never
offered to the model. Unknown tools count as outside tools, which are off unless an administrator turns them on.

Kinds and their defaults:
  read      on   search the workspace's sources, read an attached file, the knowledge graph, the person's own profile
  web       on   search the web or open a web address: it reaches outside sites, and a page can carry instructions
  generate  on   make an image (the prompt goes to the image model)
  personal  on   remember something for this person
  code      off  run Python, the coding agent, or code mode: runs code in a sandbox
  outside   off  MCP and OpenAPI tools, and any tool this list does not know: they call systems outside the product
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from evolvxsi.key_value_store.factory import get_kv_store
from evolvxsi.key_value_store.interface import KvKeyNotFoundError
from evolvxsi.utils.logger import setup_logger

logger = setup_logger()

KV_KEY = "evolvxsi_tool_catalog"
Kind = Literal["read", "web", "generate", "personal", "code", "outside"]
KINDS: tuple[Kind, ...] = ("read", "web", "generate", "personal", "code", "outside")
DEFAULTS: dict[str, bool] = {"read": True, "web": True, "generate": True, "personal": True, "code": False, "outside": False}
LABEL: dict[str, str] = {
    "read": "Read the workspace's sources and the person's files",
    "web": "Search the web or open web addresses",
    "generate": "Generate images",
    "personal": "Remember things for the person",
    "code": "Run code in a sandbox",
    "outside": "Call outside systems (MCP and OpenAPI tools)",
}

# Built-in tools by the core's id for them. Anything not listed here is treated as "outside".
BUILT_IN_KIND: dict[str, Kind] = {
    "SearchTool": "read",
    "FileReaderTool": "read",
    "KnowledgeGraphTool": "read",
    "OktaProfileTool": "read",
    "ResearchAgent": "read",  # deep research: runs the other tools the chat already has
    "WebSearchTool": "web",
    "OpenURLTool": "web",
    "ImageGenerationTool": "generate",
    "MemoryTool": "personal",
    "PythonTool": "code",
    "CodingAgentTool": "code",
}


class CatalogPolicy(BaseModel):
    version: int = 1
    kinds: dict[str, bool] = Field(default_factory=lambda: dict(DEFAULTS))
    # Per tool, by the tool's database id: True or False overrides its kind.
    tools: dict[str, bool] = Field(default_factory=dict)
    # Outside tools (MCP, OpenAPI) need their own approval, which records a hash of the tool's definition: its name,
    # description and schemas, i.e. everything the model is shown and the server is called with. A tool whose stored
    # definition no longer matches, or that a check found changed on its server, is withheld until approved again.
    pins: dict[str, str] = Field(default_factory=dict)
    drift: dict[str, str] = Field(default_factory=dict)

    def kind_on(self, kind: str) -> bool:
        return bool(self.kinds.get(kind, DEFAULTS.get(kind, False)))

    def allows(self, tool_id: int | None, kind: str) -> bool:
        if tool_id is not None and str(tool_id) in self.tools:
            return bool(self.tools[str(tool_id)])
        return self.kind_on(kind)


def load() -> CatalogPolicy:
    try:
        return CatalogPolicy.model_validate(get_kv_store().load(KV_KEY))
    except (KvKeyNotFoundError, ValueError):
        return CatalogPolicy()
    except Exception:  # noqa: BLE001 - an unreadable store falls back to the defaults, where code and outside tools are off
        logger.warning("tool catalog could not be read; using the defaults", exc_info=True)
        return CatalogPolicy()


def save(p: CatalogPolicy) -> None:
    get_kv_store().store(KV_KEY, p.model_dump())


def definition_hash(name: str | None, description: str | None, mcp_input_schema: Any, mcp_output_schema: Any, openapi_schema: Any) -> str:
    """A stable hash of what the model is shown and what the server is called with."""
    body = {"name": name or "", "description": description or "", "input": mcp_input_schema, "output": mcp_output_schema, "openapi": openapi_schema}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def outside_status(policy: "CatalogPolicy", tool_id: int, current_hash: str) -> str:
    """For an outside tool: approved, not approved, changed since approved, or changed on its server."""
    key = str(tool_id)
    if key in policy.drift:
        return "changed on its server"
    pin = policy.pins.get(key)
    if pin is None or policy.tools.get(key) is not True:
        return "not approved"
    if pin != current_hash:
        return "changed since approved"
    return "approved"


def kind_of_row(in_code_tool_id: str | None, mcp_server_id: Any, openapi_schema: Any) -> Kind:
    """The kind of a tool from its database row."""
    if mcp_server_id is not None or openapi_schema is not None:
        return "outside"
    if in_code_tool_id and in_code_tool_id in BUILT_IN_KIND:
        return BUILT_IN_KIND[in_code_tool_id]
    return "outside"


def kind_of_tool(tool: Any, rows: dict[int, tuple[str | None, Any, Any]]) -> Kind:
    """The kind of a constructed tool: by its database row when it has one, else by its class name."""
    tool_id = getattr(tool, "id", None)
    if tool_id is not None and tool_id in rows:
        return kind_of_row(*rows[tool_id])
    return BUILT_IN_KIND.get(type(tool).__name__, "outside")


def filter_tools(tools_by_id: dict[int, list[Any]], db_session: Any, policy: CatalogPolicy | None = None) -> dict[int, list[Any]]:
    """Drop the tools the catalog does not allow. Fails closed: if the check itself fails, only read tools stay."""
    from evolvxsi.db.models import Tool as ToolRow

    policy = policy or load()
    try:
        ids = [i for i in tools_by_id if i is not None]
        found = db_session.query(ToolRow.id, ToolRow.in_code_tool_id, ToolRow.mcp_server_id, ToolRow.openapi_schema, ToolRow.name,
                                 ToolRow.description, ToolRow.mcp_input_schema, ToolRow.mcp_output_schema).filter(ToolRow.id.in_(ids)).all() if ids else []
        rows = {r.id: (r.in_code_tool_id, r.mcp_server_id, r.openapi_schema) for r in found}
        hashes = {r.id: definition_hash(r.name, r.description, r.mcp_input_schema, r.mcp_output_schema, r.openapi_schema) for r in found}
    except Exception:  # noqa: BLE001
        logger.warning("tool catalog check failed; keeping only read tools for this chat", exc_info=True)
        rows, hashes, policy = {}, {}, CatalogPolicy(kinds={k: k == "read" for k in KINDS})
    out: dict[int, list[Any]] = {}
    dropped: list[str] = []
    for tool_id, tools in tools_by_id.items():
        kept = []
        for t in tools:
            kind = kind_of_tool(t, rows)
            tid = getattr(t, "id", None)
            if kind == "outside":
                # The outside switch must be on AND this tool approved with its current definition.
                status = outside_status(policy, tid, hashes.get(tid, "")) if tid is not None else "not approved"
                ok = policy.kind_on("outside") and status == "approved"
                reason = f"outside, {status}" if policy.kind_on("outside") else "outside, switched off"
            else:
                ok, reason = policy.allows(tid, kind), kind
            if ok:
                kept.append(t)
            else:
                dropped.append(f"{getattr(t, 'name', type(t).__name__)} ({reason})")
        if kept:
            out[tool_id] = kept
    if dropped:
        logger.info("tool catalog withheld from this chat: %s", ", ".join(dropped))
    return out


def code_allowed(policy: CatalogPolicy | None = None) -> bool:
    return (policy or load()).kind_on("code")
