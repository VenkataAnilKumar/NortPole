from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError

from nortpole.auth.permissions import require_permission
from nortpole.db.enums import Permission
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.extensions.policy import ExtensionPolicy, load, save
from nortpole.governance.route_policy.audit import record_audit
from nortpole.utils.audit import AuditAction, AuditOutcome

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
        raise NortPoleError(NortPoleErrorCode.VALIDATION_ERROR, str(first.get("msg", "Invalid rules")).removeprefix("Value error, ")) from e
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
