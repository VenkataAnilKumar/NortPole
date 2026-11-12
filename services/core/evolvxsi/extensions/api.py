from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.extensions.policy import ExtensionPolicy, load, save
from evolvxsi.route_policy.audit import record_audit
from evolvxsi.utils.audit import AuditAction, AuditOutcome

router = APIRouter(prefix="/admin/extensions")


class ExtensionUpdate(BaseModel):
    personal_skills: str
    mcp_allowlist_enabled: bool
    mcp_allowed_hosts: list[str]


@router.get("")
def get_extensions(_: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> ExtensionPolicy:
    return load()


@router.put("")
def put_extensions(body: ExtensionUpdate, user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> ExtensionPolicy:
    old = load()
    try:
        new = ExtensionPolicy(version=old.version + 1, personal_skills=body.personal_skills,  # type: ignore[arg-type]
                              mcp_allowlist_enabled=body.mcp_allowlist_enabled, mcp_allowed_hosts=body.mcp_allowed_hosts)
    except ValidationError as e:
        first = e.errors()[0]
        raise EvolvXSIError(EvolvXSIErrorCode.VALIDATION_ERROR, str(first.get("msg", "Invalid rules")).removeprefix("Value error, ")) from e
    save(new)
    bits = []
    if old.personal_skills != new.personal_skills:
        bits.append(f"personal skills {old.personal_skills} to {new.personal_skills}")
    if old.mcp_allowlist_enabled != new.mcp_allowlist_enabled:
        bits.append("MCP allowlist " + ("on" if new.mcp_allowlist_enabled else "off"))
    added, removed = set(new.mcp_allowed_hosts) - set(old.mcp_allowed_hosts), set(old.mcp_allowed_hosts) - set(new.mcp_allowed_hosts)
    if added or removed:
        bits.append("MCP hosts " + " ".join([f"+{h}" for h in sorted(added)] + [f"-{h}" for h in sorted(removed)]))
    record_audit(AuditAction.EXTENSION_CHANGE, AuditOutcome.SUCCESS, actor=user, resource_type="extensions",
                 summary="Extension rules changed: " + ("; ".join(bits) or "no change"))
    return new
