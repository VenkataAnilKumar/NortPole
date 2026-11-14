from __future__ import annotations

import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from evolvxsi.work.actions.models import EvolvXSIAction, EvolvXSIActionTarget
from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import LLMProvider, MCPServer, Skill, User
from evolvxsi.extensions.policy import host_allowed, load as load_extensions
from evolvxsi.work.packs.api import current_model, passed_on_current_model
from evolvxsi.work.packs.models import EvolvXSIPackSigner, EvolvXSIPackVersion
from evolvxsi.governance.route_policy.policy import kind_for, load_policy
from evolvxsi.governance.route_policy.usage import EvolvXSIRouteUsage
from evolvxsi.work.tasks.models import EvolvXSITask

router = APIRouter(prefix="/admin/inventory")
NOT_RECORDED = "not recorded"


class Item(BaseModel):
    kind: str            # pack | destination | model_route | skill | mcp_server
    name: str
    detail: str          # one line: what it is
    status: str          # active, disabled, revoked, invalid, ...
    owner: str | None
    version: str | None
    last_use: str | None  # ISO time, or "not recorded"
    uses: int | None      # a count where one is kept
    notes: list[str]


class Inventory(BaseModel):
    generated_at: str
    items: list[Item]
    counts: dict[str, int]
    limits: list[str]


def host_only(url: str | None) -> str:
    """The host of a URL and nothing else: a path, query or user info can carry a secret."""
    try:
        return urlparse(url or "").hostname or "unknown host"
    except ValueError:
        return "unknown host"


def _iso(d: datetime.datetime | datetime.date | None) -> str | None:
    return d.isoformat() if d else None


def build(db: Session) -> Inventory:
    items: list[Item] = []
    policy = load_policy()

    # Packs: only versions that are active (what people can use now).
    for v in db.scalars(select(EvolvXSIPackVersion).where(EvolvXSIPackVersion.active.is_(True)).order_by(EvolvXSIPackVersion.pack_id)):
        m = v.manifest
        signer = db.scalar(select(EvolvXSIPackSigner).where(EvolvXSIPackSigner.key_id == v.signer_key_id))
        ready, why = passed_on_current_model(db, v.pack_id, v.version, m)
        n, last = db.execute(select(func.count(EvolvXSITask.id), func.max(EvolvXSITask.created_at)).where(EvolvXSITask.pack_id == v.pack_id)).one()
        revoked = signer is None or signer.revoked
        notes = [f"autonomy: {m.get('autonomy', 'act_with_approval')}", f"signed by {v.signer_key_id}"]
        if not ready:
            notes.append(f"not offered on the current model: {why}")
        items.append(Item(kind="pack", name=m.get("name", v.pack_id), detail=f"{len(m.get('templates', []))} templates, vertical {m.get('vertical', '?')}",
                          status="signer revoked" if revoked else "active", owner=None, version=v.version,
                          last_use=_iso(last) if n else NOT_RECORDED, uses=int(n), notes=notes))

    # Send destinations, with the last successful send.
    for t in db.scalars(select(EvolvXSIActionTarget).order_by(EvolvXSIActionTarget.name)):
        n, last = db.execute(select(func.count(EvolvXSIAction.id), func.max(EvolvXSIAction.executed_at)).where(
            EvolvXSIAction.target_id == t.id, EvolvXSIAction.state == "succeeded")).one()
        items.append(Item(kind="destination", name=t.name, detail=f"{t.kind} destination", status="active" if t.enabled else "disabled",
                          owner=None, version=None, last_use=_iso(last) if n else NOT_RECORDED, uses=int(n),
                          notes=[f"tier: {t.tier}", "may receive: " + (", ".join(t.allowed_data_classes or []) or "nothing")]))

    # Model routes, with 30 days of request counts.
    since = datetime.date.today() - datetime.timedelta(days=29)
    default = current_model(db)
    for p in db.scalars(select(LLMProvider).order_by(LLMProvider.id)):
        n, last = db.execute(select(func.coalesce(func.sum(EvolvXSIRouteUsage.requests), 0), func.max(EvolvXSIRouteUsage.day)).where(
            EvolvXSIRouteUsage.provider_id == p.id, EvolvXSIRouteUsage.day >= since)).one()
        kind = kind_for(policy, p.id)
        notes = [f"route kind: {kind}" + ("" if str(p.id) in policy.route_kinds else " (not assigned: treated as cloud)"),
                 "redaction: " + ("on" if kind in policy.redact_route_kinds else "off")]
        if default is not None and default.llm_provider_id == p.id:
            notes.append(f"default model: {default.name}")
        items.append(Item(kind="model_route", name=p.name, detail=p.provider, status="active", owner=None, version=None,
                          last_use=_iso(last) if last else NOT_RECORDED, uses=int(n), notes=notes + ["request count covers the last 30 days"]))

    # Skills and MCP servers come from the core; no use is recorded for them.
    for sk in db.scalars(select(Skill).order_by(Skill.name)):
        items.append(Item(kind="skill", name=sk.name, detail=(sk.description or "")[:120], status="invalid" if sk.is_valid is False else "active",
                          owner=None, version=None, last_use=NOT_RECORDED, uses=None,
                          notes=[f"installation policy: {getattr(sk.installation_policy, 'value', sk.installation_policy)}"]))
    ext = load_extensions()
    for s in db.scalars(select(MCPServer).order_by(MCPServer.name)):
        host = host_only(s.server_url)
        items.append(Item(kind="mcp_server", name=s.name, detail=f"MCP server at {host}", status=str(getattr(s.status, "value", s.status)).lower(),
                          owner=s.owner, version=None, last_use=NOT_RECORDED, uses=None,
                          notes=[f"transport: {getattr(s.transport, 'value', s.transport)}",
                                 "allowlist: off" if not ext.mcp_allowlist_enabled else ("host allowed" if host_allowed(s.server_url, ext) else "NOT on the allowlist: calls are blocked")]))

    counts: dict[str, int] = {}
    for i in items:
        counts[i.kind] = counts.get(i.kind, 0) + 1
    return Inventory(
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), items=items, counts=counts,
        limits=["Last use is recorded only for packs (tasks started), destinations (successful sends) and model routes (request counts); skills and MCP servers show 'not recorded'.",
                "Only active pack versions are listed. Plugins, custom tools and connectors are not listed here."],
    )


@router.get("")
def get_inventory(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> Inventory:
    return build(db_session)
