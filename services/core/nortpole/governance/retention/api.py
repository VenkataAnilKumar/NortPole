from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.retention.prune import prune
from nortpole.governance.retention.settings import MAX_DAYS, MIN_DAYS, Retention, load, save
from nortpole.governance.route_policy.audit import record_audit
from nortpole.utils.audit import AuditAction, AuditOutcome

router = APIRouter(prefix="/admin/retention")


class RetentionView(BaseModel):
    audit_days: int | None
    usage_days: int | None
    legal_hold: bool
    hold_reason: str
    hold_set_by: str | None
    last_prune_at: str | None
    last_prune_summary: str | None
    min_days: int = MIN_DAYS
    max_days: int = MAX_DAYS
    placeholder_note: str = "The default periods are placeholders, not agreed with anyone and not checked against any legal requirement."


class RetentionUpdate(BaseModel):
    audit_days: int | None = Field(default=None, ge=MIN_DAYS, le=MAX_DAYS)
    usage_days: int | None = Field(default=None, ge=MIN_DAYS, le=MAX_DAYS)
    keep_audit_forever: bool = False
    keep_usage_forever: bool = False
    legal_hold: bool = False
    hold_reason: str = Field(default="", max_length=500)


def _view(r: Retention) -> RetentionView:
    return RetentionView(**r.model_dump(exclude={"version"}))


@router.get("")
def get_retention(_: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> RetentionView:
    return _view(load())


def plan_retention_update(body: RetentionUpdate, proposer_email: str | None) -> tuple[Retention, Retention]:
    """The settings as they are now and as they would be after this update. Raises if the update is not valid."""
    if body.legal_hold and not body.hold_reason.strip():
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "A legal hold needs a reason.")
    old = load()
    new = old.model_copy(update={
        "version": old.version + 1,
        "audit_days": None if body.keep_audit_forever else (body.audit_days or old.audit_days),
        "usage_days": None if body.keep_usage_forever else (body.usage_days or old.usage_days),
        "legal_hold": body.legal_hold,
        "hold_reason": body.hold_reason.strip() if body.legal_hold else "",
        "hold_set_by": (proposer_email if body.legal_hold and not old.legal_hold else (old.hold_set_by if body.legal_hold else None)),
    })
    return old, new


def retention_summary(old: Retention, new: Retention) -> str:
    bits = []
    if (old.audit_days, old.usage_days) != (new.audit_days, new.usage_days):
        bits.append(f"periods audit {old.audit_days} to {new.audit_days} days, usage {old.usage_days} to {new.usage_days} days")
    if old.legal_hold != new.legal_hold:
        bits.append("legal hold placed: " + new.hold_reason if new.legal_hold else "legal hold lifted")
    return "Retention changed: " + ("; ".join(bits) or "no change")


def apply_retention_update(
    body: RetentionUpdate, actor: User | None, *, proposer_email: str | None = None,
    approver_email: str | None = None, expect_version: int | None = None,
) -> Retention:
    """Save the update and audit it. `expect_version` refuses it if the settings changed since it was proposed."""
    old, new = plan_retention_update(body, proposer_email or getattr(actor, "email", None))
    if expect_version is not None and old.version != expect_version:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The retention settings changed after this was proposed. Propose it again.")
    save(new)
    summary = retention_summary(old, new)
    details = {"proposed_by": proposer_email or getattr(actor, "email", None), "approved_by": approver_email} if approver_email else None
    record_audit(AuditAction.RETENTION_CHANGE, AuditOutcome.SUCCESS, actor=actor, summary=summary, details=details, resource_type="retention")
    return new


@router.put("")
def put_retention(
    body: RetentionUpdate,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> RetentionView:
    from nortpole.governance.admin_changes import controls
    from nortpole.governance.admin_changes.service import propose, pending_response

    if controls.required("retention"):
        old, new = plan_retention_update(body, getattr(user, "email", None))
        return pending_response(propose(db_session, user, "retention", body.model_dump(), old.version, retention_summary(old, new)))  # type: ignore[return-value]
    return _view(apply_retention_update(body, user))


@router.post("/prune")
def run_prune(
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> dict:
    """Run the prune now. Under a legal hold it does nothing and says so."""
    return prune(db_session, actor=user)
