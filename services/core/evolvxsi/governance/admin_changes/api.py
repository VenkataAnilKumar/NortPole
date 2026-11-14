"""Administrator changes that wait for a second administrator, and the rules that say which ones do."""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from evolvxsi.governance.admin_changes import controls, service
from evolvxsi.governance.admin_changes.models import EvolvXSIAdminChange
from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User

router = APIRouter(prefix="/admin")


class ChangeView(BaseModel):
    id: UUID
    kind: str
    summary: str
    state: str
    proposed_by_email: str
    decided_by_email: str | None
    error: str | None
    created_at: datetime.datetime
    decided_at: datetime.datetime | None
    own: bool


class ChangesView(BaseModel):
    pending: list[ChangeView]
    recent: list[ChangeView]


def _view(c: EvolvXSIAdminChange, user: User) -> ChangeView:
    return ChangeView(id=c.id, kind=c.kind, summary=c.summary, state=c.state, proposed_by_email=c.proposed_by_email,
                      decided_by_email=c.decided_by_email, error=c.error, created_at=c.created_at, decided_at=c.decided_at,
                      own=c.proposed_by_id == user.id)


@router.get("/changes")
def list_changes(
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ChangesView:
    # A GET never writes (route contract). A pending change past its 7 days is shown as expired here; its stored
    # state is updated the next time anyone approves, declines or proposes a change (service.expire_old).
    cutoff = service._now() - service.EXPIRES_AFTER
    pending = db_session.scalars(select(EvolvXSIAdminChange).where(EvolvXSIAdminChange.state == "pending").order_by(EvolvXSIAdminChange.created_at)).all()
    recent = db_session.scalars(select(EvolvXSIAdminChange).where(EvolvXSIAdminChange.state != "pending").order_by(EvolvXSIAdminChange.decided_at.desc()).limit(10)).all()
    live = [_view(c, user) for c in pending if c.created_at >= cutoff]
    overdue = [_view(c, user).model_copy(update={"state": "expired", "error": "Nobody approved it within 7 days.",
                                                  "decided_at": c.created_at + service.EXPIRES_AFTER})
               for c in pending if c.created_at < cutoff]
    done = sorted(overdue + [_view(c, user) for c in recent], key=lambda v: v.decided_at or v.created_at, reverse=True)[:10]
    return ChangesView(pending=live, recent=done)


@router.post("/changes/{change_id}/approve")
def approve_change(
    change_id: UUID,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ChangeView:
    return _view(service.approve(db_session, user, change_id), user)


@router.post("/changes/{change_id}/decline")
def decline_change(
    change_id: UUID,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ChangeView:
    return _view(service.decline(db_session, user, change_id), user)


@router.post("/changes/{change_id}/cancel")
def cancel_change(
    change_id: UUID,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ChangeView:
    return _view(service.cancel(db_session, user, change_id), user)


class ControlsUpdate(BaseModel):
    second_for_route_policy: bool
    second_for_retention: bool


@router.get("/controls")
def get_controls(_: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> controls.AdminControls:
    return controls.load()


@router.put("/controls")
def put_controls(
    body: ControlsUpdate,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
):  # type: ignore[no-untyped-def]
    """Choose which administrator changes need a second administrator. With every rule off, any change takes effect at
    once (including turning rules on). With any rule on, changing the rules itself needs a second administrator."""
    current = controls.load()
    wanted = {"second_for_route_policy": body.second_for_route_policy, "second_for_retention": body.second_for_retention}
    summary = "Second-administrator rules: route policy " + ("on" if wanted["second_for_route_policy"] else "off") + ", retention " + ("on" if wanted["second_for_retention"] else "off")
    if controls.required("controls"):
        return service.pending_response(service.propose(db_session, user, "controls", wanted, current.version, summary))
    new = controls.AdminControls(version=current.version + 1, **wanted)
    controls.save(new)
    from evolvxsi.governance.route_policy.audit import record_audit
    from evolvxsi.utils.audit import AuditAction, AuditOutcome

    record_audit(AuditAction.ADMIN_CHANGE_DECIDE, AuditOutcome.SUCCESS, actor=user, summary=summary, resource_type="admin_controls")
    return new
