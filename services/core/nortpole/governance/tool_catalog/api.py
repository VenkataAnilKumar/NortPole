"""The tool catalog for administrators: every tool chat agents could be given, its kind, whether the catalog allows
it, and which agents have it. Changing it is audited."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.configs.chat_configs import CODE_MODE_ENABLED
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission
from nortpole.db.models import MCPServer, Persona, Persona__Tool, Tool, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.audit import record_audit
from nortpole.governance.tool_catalog import catalog
from nortpole.utils.audit import AuditAction, AuditOutcome

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
    # Outside tools only: approved, not approved, changed since approved, or changed on its server; and what is approved.
    approval: str | None = None
    server_id: int | None = None  # for an MCP tool, so its server can be checked
    description: str = ""
    definition_preview: str = ""

    @property
    def workspace_request_key(self) -> str | None:
        if self.personal or (self.allowed and self.core_enabled):
            return None
        return str(self.id)


class CatalogView(BaseModel):
    version: int
    kinds: list[KindView]
    tools: list[ToolView]
    code_mode_switched_on: bool  # the core's code mode needs both its own setting and the "code" kind


class CatalogUpdate(BaseModel):
    kinds: dict[str, bool]
    tools: dict[str, bool] = Field(default_factory=dict)
    # Outside tools to approve again with their definition as it is now (after a change). Saving other settings never
    # does this: an existing approval keeps the definition it was given for.
    approve: list[str] = Field(default_factory=list)


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
        current = catalog.definition_hash(t.name, t.description, t.mcp_input_schema, t.mcp_output_schema, t.openapi_schema)
        approval = catalog.outside_status(p, t.id, current) if kind == "outside" else None
        schema = t.mcp_input_schema if t.mcp_server_id is not None else t.openapi_schema
        source = "MCP" if t.mcp_server_id is not None else "OpenAPI" if t.openapi_schema is not None else "built-in"
        tools.append(ToolView(
            id=t.id, name=t.display_name or t.name, kind=kind, source=source,
            host=servers.get(t.mcp_server_id) if t.mcp_server_id is not None else None,
            core_enabled=bool(t.enabled),
            allowed=(p.kind_on("outside") and approval == "approved") if kind == "outside" else p.allows(t.id, kind),
            override=p.tools.get(str(t.id)), approval=approval, server_id=t.mcp_server_id,
            description=(t.description or "")[:2000] if kind == "outside" else "",
            definition_preview=json.dumps(schema, indent=1, sort_keys=True, default=str)[:3000] if kind == "outside" and schema is not None else "",
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


def _check_update(body: CatalogUpdate, db_session: Session) -> None:
    unknown = set(body.kinds) - set(catalog.KINDS)
    if unknown:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, f"Unknown tool kind: {', '.join(sorted(unknown))}")
    ids = {str(i) for i in db_session.scalars(select(Tool.id))}
    bad = [k for k in body.tools if k not in ids]
    if bad:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, f"Unknown tool id: {', '.join(sorted(bad))}")
    bad = [k for k in body.approve if body.tools.get(k) is not True]
    if bad:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, f"A tool must be on to be approved again: {', '.join(bad)}")


def apply_catalog_update(body: CatalogUpdate, db_session: Session, user: User | None, *, approver_email: str | None = None,
                         expect_version: int | None = None) -> CatalogView:
    _check_update(body, db_session)
    old = catalog.load()
    if expect_version is not None and old.version != expect_version:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The tool catalog changed after this was proposed. Propose it again.")
    tools = {k: bool(v) for k, v in body.tools.items()}
    # Approving an outside tool records its current definition; anything else about it drops the record.
    rows = {str(t.id): t for t in db_session.scalars(select(Tool).where(Tool.id.in_([int(k) for k in tools]))) } if tools else {}
    pins: dict[str, str] = {}
    drift = dict(old.drift)
    for k, v in tools.items():
        t = rows[k]
        if catalog.kind_of_row(t.in_code_tool_id, t.mcp_server_id, t.openapi_schema) != "outside" or not v:
            continue
        current = catalog.definition_hash(t.name, t.description, t.mcp_input_schema, t.mcp_output_schema, t.openapi_schema)
        if k in body.approve or old.tools.get(k) is not True or k not in old.pins:
            pins[k] = current  # a new approval, or an explicit approval again: of the definition as it is now
            drift.pop(k, None)
        else:
            pins[k] = old.pins[k]  # an existing approval keeps the definition it was given for
    drift = {k: v for k, v in drift.items() if k in pins}
    new = catalog.CatalogPolicy(version=old.version + 1, kinds={k: bool(body.kinds.get(k, old.kind_on(k))) for k in catalog.KINDS},
                                tools=tools, pins=pins, drift=drift)
    catalog.save(new)
    bits = [f"{k} {'on' if new.kinds[k] else 'off'}" for k in catalog.KINDS if new.kinds[k] != old.kind_on(k)]
    for k in sorted(set(old.tools) | set(new.tools), key=int):
        if old.tools.get(k) != new.tools.get(k):
            v = new.tools.get(k)
            bits.append(f"tool {k} {'follows its kind' if v is None else 'on' if v else 'off'}")
    for k in sorted(set(new.pins) - set(old.pins) | {k for k in new.pins if old.pins.get(k) not in (None, new.pins[k])}, key=int):
        bits.append(f"tool {k} approved with definition {new.pins[k][:12]}")
    record_audit(AuditAction.EXTENSION_CHANGE, AuditOutcome.SUCCESS, actor=user, resource_type="tool_catalog",
                 summary="Tool catalog changed: " + ("; ".join(bits) or "no change")
                 + (f" (second administrator {approver_email})" if approver_email else ""))
    return build(db_session)


@router.put("")
def put_catalog(
    body: CatalogUpdate,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
):  # type: ignore[no-untyped-def]
    from nortpole.governance.admin_changes import controls
    from nortpole.governance.admin_changes.service import pending_response, propose

    if controls.required("tool_catalog"):
        # Refuse mistakes now, in a transaction that is rolled back; only a valid change is held.
        _check_update(body, db_session)
        old = catalog.load()
        return pending_response(propose(db_session, user, "tool_catalog", body.model_dump(), old.version, "Change the tool catalog"))
    return apply_catalog_update(body, db_session, user)


class CheckResult(BaseModel):
    tool_id: int | None
    name: str
    status: str  # unchanged, changed on its server, missing on the server, new on the server (not stored)


@router.post("/check/{server_id}")
def check_server(
    server_id: int,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[CheckResult]:
    """Ask an MCP server for its tools now, without saving anything, and compare them with what was approved.
    An approved tool whose definition differs on the server is withheld until an administrator refreshes the server's
    tools and approves it again. The result is audited."""
    from nortpole.server.features.mcp.api import _discover_mcp_server_tools

    _, live = _discover_mcp_server_tools(server_id, db_session, True, user)
    live_by_name = {t.name: t for t in live}
    stored = list(db_session.scalars(select(Tool).where(Tool.mcp_server_id == server_id)))
    p = catalog.load()
    out: list[CheckResult] = []
    drift = dict(p.drift)
    for t in stored:
        lt = live_by_name.get(t.name)
        if lt is None:
            status = "missing on the server"
            if str(t.id) in p.pins:
                drift[str(t.id)] = "missing on its server"
        else:
            live_hash = catalog.definition_hash(lt.name, lt.description or "", lt.inputSchema, getattr(lt, "outputSchema", None), None)
            if live_hash != catalog.definition_hash(t.name, t.description, t.mcp_input_schema, t.mcp_output_schema, None) or \
               (str(t.id) in p.pins and live_hash != p.pins[str(t.id)]):
                status = "changed on its server"
                if str(t.id) in p.pins:
                    drift[str(t.id)] = "changed on its server"
            else:
                status = "unchanged"
        out.append(CheckResult(tool_id=t.id, name=t.name, status=status))
    for name in sorted(set(live_by_name) - {t.name for t in stored}):
        out.append(CheckResult(tool_id=None, name=name, status="new on the server (not stored)"))
    if drift != p.drift:
        catalog.save(p.model_copy(update={"version": p.version + 1, "drift": drift}))
    changed = [r.name for r in out if r.status != "unchanged"]
    record_audit(AuditAction.EXTENSION_CHANGE, AuditOutcome.SUCCESS if not changed else AuditOutcome.FAILURE, actor=user,
                 resource_type="tool_catalog", resource_id=server_id,
                 summary=f"Checked MCP server {server_id}: {len(out)} tool(s), " + (f"differences: {', '.join(changed)[:300]}" if changed else "no differences"))
    return out


member_router = APIRouter(prefix="/tool-catalog")


class MemberToolView(BaseModel):
    name: str
    kind_label: str
    allowed: bool
    mine: bool  # a personal tool this person added
    workspace_request_key: str | None = None


class MemberCatalogView(BaseModel):
    kinds: list[KindView]
    tools: list[MemberToolView]


@member_router.get("")
def get_member_catalog(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MemberCatalogView:
    """Tool availability and workspace request keys. Personal tools are visible only to their owners."""
    view = build(db_session)
    rows = {t.id: t for t in db_session.scalars(select(Tool))}
    tools = []
    for t in view.tools:
        owner = rows[t.id].user_id if t.id in rows else None
        if owner is not None and owner != user.id:
            continue
        tools.append(MemberToolView(
            name=t.name,
            kind_label=catalog.LABEL[t.kind],
            allowed=t.allowed and t.core_enabled,
            mine=owner is not None,
            workspace_request_key=t.workspace_request_key,
        ))
    return MemberCatalogView(kinds=view.kinds, tools=tools)
