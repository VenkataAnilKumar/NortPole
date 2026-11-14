from __future__ import annotations

from fastapi import Depends

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.extensions.policy import host_allowed, host_of, load
from evolvxsi.governance.route_policy.audit import record_audit
from evolvxsi.utils.audit import AuditAction, AuditOutcome


def assert_mcp_url_allowed(url: str | None, user: User | None) -> None:
    """Refuse (and audit) an MCP server whose host is not on the allowlist."""
    if host_allowed(url):
        return
    record_audit(AuditAction.EXTENSION_BLOCKED, AuditOutcome.DENIED, actor=user, resource_type="mcp_server",
                 summary=f"MCP server at {host_of(url) or 'an unreadable address'} refused: not on the allowlist")
    raise EvolvXSIError(EvolvXSIErrorCode.POLICY_BLOCKED,
                        f"The host {host_of(url) or '(unreadable)'} is not on this workspace's MCP allowlist. Ask an administrator to add it.")


def personal_skills_allowed(user: User = Depends(require_permission(Permission.BASIC_ACCESS))) -> None:
    """Dependency for the routes that add or change a personal skill."""
    if load().personal_skills == "off":
        record_audit(AuditAction.EXTENSION_BLOCKED, AuditOutcome.DENIED, actor=user, resource_type="skill",
                     summary="Adding a personal skill refused: personal skills are off")
        raise EvolvXSIError(EvolvXSIErrorCode.POLICY_BLOCKED, "Personal skills are turned off in this workspace. Ask an administrator.")
