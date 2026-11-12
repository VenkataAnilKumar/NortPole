from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.retention.prune import prune
from evolvxsi.retention.settings import MAX_DAYS, MIN_DAYS, Retention, load, save
from evolvxsi.route_policy.audit import record_audit
from evolvxsi.utils.audit import AuditAction, AuditOutcome

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


@router.put("")
def put_retention(
    body: RetentionUpdate,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> RetentionView:
    if body.legal_hold and not body.hold_reason.strip():
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "A legal hold needs a reason.")
    old = load()
    new = old.model_copy(update={
        "version": old.version + 1,
        "audit_days": None if body.keep_audit_forever else (body.audit_days or old.audit_days),
        "usage_days": None if body.keep_usage_forever else (body.usage_days or old.usage_days),
        "legal_hold": body.legal_hold,
        "hold_reason": body.hold_reason.strip() if body.legal_hold else "",
        "hold_set_by": (getattr(user, "email", None) if body.legal_hold and not old.legal_hold else (old.hold_set_by if body.legal_hold else None)),
    })
    save(new)
    bits = []
    if (old.audit_days, old.usage_days) != (new.audit_days, new.usage_days):
        bits.append(f"periods audit {old.audit_days} to {new.audit_days} days, usage {old.usage_days} to {new.usage_days} days")
    if old.legal_hold != new.legal_hold:
        bits.append("legal hold placed: " + new.hold_reason if new.legal_hold else "legal hold lifted")
    record_audit(AuditAction.RETENTION_CHANGE, AuditOutcome.SUCCESS, actor=user,
                 summary="Retention changed: " + ("; ".join(bits) or "no change"), resource_type="retention")
    return _view(new)


@router.post("/prune")
def run_prune(
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> dict:
    """Run the prune now. Under a legal hold it does nothing and says so."""
    return prune(db_session, actor=user)
