"""The tool catalog for administrators: every tool chat agents could be given, its kind, whether the catalog allows
it, and which agents have it. Changing it is audited."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.configs.chat_configs import CODE_MODE_ENABLED
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import MCPServer, Persona, Persona__Tool, Tool, User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.route_policy.audit import record_audit
from evolvxsi.tool_catalog import catalog
from evolvxsi.utils.audit import AuditAction, AuditOutcome

router = APIRouter(prefix="/admin/tool-catalog")


class KindView(BaseModel):
    kind: str
    label: str
    on: bool
    default: bool


class ToolView(BaseModel):
    id: int
    name: str
    kind: str
    source: str  # built-in, MCP or OpenAPI
    host: str | None  # for an MCP server, its host only (a URL can hold a secret)
    core_enabled: bool  # the core's own switch for this tool
    allowed: bool  # what the catalog says
    override: bool | None  # a per-tool setting, if any
    personal: bool  # added by one person for themselves
    agents: int  # chat agents that have it attached
    agent_names: list[str]


class CatalogView(BaseModel):
    version: int
    kinds: list[KindView]
    tools: list[ToolView]
    code_mode_switched_on: bool  # the core's code mode needs both its own setting and the "code" kind


class CatalogUpdate(BaseModel):
    kinds: dict[str, bool]
    tools: dict[str, bool] = Field(default_factory=dict)


def build(db: Session) -> CatalogView:
    p = catalog.load()
    counts = dict(db.execute(select(Persona__Tool.tool_id, func.count()).join(Persona, Persona.id == Persona__Tool.persona_id)
                             .where(Persona.deleted.is_(False)).group_by(Persona__Tool.tool_id)).all())
    names: dict[int, list[str]] = {}
    for tid, pname in db.execute(select(Persona__Tool.tool_id, Persona.name).join(Persona, Persona.id == Persona__Tool.persona_id)
                                 .where(Persona.deleted.is_(False)).order_by(Persona.name)):
        names.setdefault(tid, []).append(pname)
    servers = {s.id: urlparse(s.server_url).hostname for s in db.scalars(select(MCPServer))}
    tools = []
    for t in db.scalars(select(Tool).order_by(Tool.id)):
        kind = catalog.kind_of_row(t.in_code_tool_id, t.mcp_server_id, t.openapi_schema)
        source = "MCP" if t.mcp_server_id is not None else "OpenAPI" if t.openapi_schema is not None else "built-in"
        tools.append(ToolView(
            id=t.id, name=t.display_name or t.name, kind=kind, source=source,
            host=servers.get(t.mcp_server_id) if t.mcp_server_id is not None else None,
            core_enabled=bool(t.enabled), allowed=p.allows(t.id, kind), override=p.tools.get(str(t.id)),
            personal=t.user_id is not None, agents=int(counts.get(t.id, 0)), agent_names=names.get(t.id, [])[:5],
        ))
    kinds = [KindView(kind=k, label=catalog.LABEL[k], on=p.kind_on(k), default=catalog.DEFAULTS[k]) for k in catalog.KINDS]
    return CatalogView(version=p.version, kinds=kinds, tools=tools, code_mode_switched_on=CODE_MODE_ENABLED)


@router.get("")
def get_catalog(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> CatalogView:
    return build(db_session)


@router.put("")
def put_catalog(
    body: CatalogUpdate,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> CatalogView:
    unknown = set(body.kinds) - set(catalog.KINDS)
    if unknown:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, f"Unknown tool kind: {', '.join(sorted(unknown))}")
    ids = {str(i) for i in db_session.scalars(select(Tool.id))}
    bad = [k for k in body.tools if k not in ids]
    if bad:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, f"Unknown tool id: {', '.join(sorted(bad))}")
    old = catalog.load()
    new = catalog.CatalogPolicy(version=old.version + 1, kinds={k: bool(body.kinds.get(k, old.kind_on(k))) for k in catalog.KINDS},
                                tools={k: bool(v) for k, v in body.tools.items()})
    catalog.save(new)
    bits = [f"{k} {'on' if new.kinds[k] else 'off'}" for k in catalog.KINDS if new.kinds[k] != old.kind_on(k)]
    for k in sorted(set(old.tools) | set(new.tools), key=int):
        if old.tools.get(k) != new.tools.get(k):
            v = new.tools.get(k)
            bits.append(f"tool {k} {'follows its kind' if v is None else 'on' if v else 'off'}")
    record_audit(AuditAction.EXTENSION_CHANGE, AuditOutcome.SUCCESS, actor=user, resource_type="tool_catalog",
                 summary="Tool catalog changed: " + ("; ".join(bits) or "no change"))
    return build(db_session)
