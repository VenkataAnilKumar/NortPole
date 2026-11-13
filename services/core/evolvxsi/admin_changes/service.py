"""Proposing, approving and declining administrator changes that need a second administrator."""

from __future__ import annotations

import datetime
from typing import Any

from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from evolvxsi.admin_changes import controls
from evolvxsi.admin_changes.models import EvolvXSIAdminChange
from evolvxsi.db.models import User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.route_policy.audit import record_audit
from evolvxsi.utils.audit import AuditAction, AuditOutcome

EXPIRES_AFTER = datetime.timedelta(days=7)
MAX_PENDING = 50  # a ceiling, so a runaway client cannot fill the table


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def propose(db: Session, user: User, kind: str, payload: dict[str, Any], base_version: int, summary: str) -> EvolvXSIAdminChange:
    if kind not in controls.KINDS:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "Unknown kind of change.")
    pending = db.scalars(select(EvolvXSIAdminChange).where(EvolvXSIAdminChange.state == "pending")).all()
    if len(pending) >= MAX_PENDING:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Too many changes are waiting. Approve, decline or cancel some first.")
    # One waiting change per kind and person: a newer proposal replaces the older one instead of piling up.
    for old in pending:
        if old.kind == kind and old.proposed_by_id == user.id:
            old.state, old.decided_at, old.error = "cancelled", _now(), "Replaced by a newer proposal."
    change = EvolvXSIAdminChange(kind=kind, payload=payload, summary=summary[:1000], base_version=base_version,
                                 proposed_by_id=user.id, proposed_by_email=user.email)
    db.add(change)
    db.commit()
    record_audit(AuditAction.ADMIN_CHANGE_PROPOSE, AuditOutcome.SUCCESS, actor=user,
                 summary=f"Proposed, waiting for a second administrator: {change.summary}",
                 details={"kind": kind, "change_id": str(change.id), "base_version": base_version},
                 resource_type="admin_change", resource_id=str(change.id))
    return change


def pending_response(change: EvolvXSIAdminChange) -> JSONResponse:
    """What the original endpoint returns instead of its usual body, so callers can tell the change was not applied."""
    return JSONResponse(status_code=202, content={
        "pending_approval": True, "change_id": str(change.id), "kind": change.kind, "summary": change.summary,
        "message": "This change was not applied. It waits for a second administrator to approve it.",
    })


def expire_old(db: Session) -> None:
    cutoff = _now() - EXPIRES_AFTER
    changed = False
    for c in db.scalars(select(EvolvXSIAdminChange).where(EvolvXSIAdminChange.state == "pending", EvolvXSIAdminChange.created_at < cutoff)):
        c.state, c.decided_at, c.error = "expired", _now(), "Nobody approved it within 7 days."
        changed = True
    if changed:
        db.commit()


def _get(db: Session, change_id: Any) -> EvolvXSIAdminChange:
    c = db.get(EvolvXSIAdminChange, change_id)
    if c is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Change not found.")
    return c


def _audit_decision(approver: User, c: EvolvXSIAdminChange, summary: str, outcome: AuditOutcome) -> None:
    record_audit(AuditAction.ADMIN_CHANGE_DECIDE, outcome, actor=approver, summary=summary,
                 details={"kind": c.kind, "change_id": str(c.id), "proposed_by": c.proposed_by_email},
                 resource_type="admin_change", resource_id=str(c.id))


def _apply(db: Session, c: EvolvXSIAdminChange, approver: User) -> None:
    """Run the change the way its own endpoint would have, now, as approved. Raises if it is no longer valid."""
    proposer = db.get(User, c.proposed_by_id) if c.proposed_by_id else None
    if c.kind == "route_policy":
        from evolvxsi.route_policy.api import RoutePolicyUpdate, apply_policy_update

        apply_policy_update(RoutePolicyUpdate(**c.payload), db, proposer, approver_email=approver.email, expect_version=c.base_version)
    elif c.kind == "retention":
        from evolvxsi.retention.api import RetentionUpdate, apply_retention_update

        apply_retention_update(RetentionUpdate(**c.payload), proposer, proposer_email=c.proposed_by_email,
                               approver_email=approver.email, expect_version=c.base_version)
    elif c.kind == "controls":
        current = controls.load()
        if current.version != c.base_version:
            raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "The approval rules changed after this was proposed. Propose it again.")
        new = controls.AdminControls(version=current.version + 1, **{k: bool(v) for k, v in c.payload.items() if k in controls.AdminControls.model_fields and k != "version"})
        controls.save(new)
        record_audit(AuditAction.ADMIN_CHANGE_DECIDE, AuditOutcome.SUCCESS, actor=proposer,
                     summary=f"Approval rules changed: {c.summary}", resource_type="admin_controls",
                     details={"proposed_by": c.proposed_by_email, "approved_by": approver.email})
    else:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "Unknown kind of change.")


def approve(db: Session, approver: User, change_id: Any) -> EvolvXSIAdminChange:
    expire_old(db)
    c = _get(db, change_id)
    if c.state != "pending":
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, f"A change that is {c.state} cannot be approved.")
    if c.proposed_by_id == approver.id:
        _audit_decision(approver, c, f"Approval refused: the approver proposed it ({c.summary})", AuditOutcome.DENIED)
        raise EvolvXSIError(EvolvXSIErrorCode.INSUFFICIENT_PERMISSIONS, "A different administrator has to approve this change.")
    try:
        _apply(db, c, approver)
    except EvolvXSIError as e:
        db.rollback()
        c = _get(db, change_id)
        c.state, c.decided_at, c.decided_by_email, c.error = "failed", _now(), approver.email, str(e.detail)[:500]
        db.commit()
        _audit_decision(approver, c, f"Approval could not be applied: {c.error}", AuditOutcome.FAILURE)
        raise
    c = _get(db, change_id)
    c.state, c.decided_at, c.decided_by_email = "applied", _now(), approver.email
    db.commit()
    _audit_decision(approver, c, f"Approved and applied: {c.summary}", AuditOutcome.SUCCESS)
    return c


def decline(db: Session, approver: User, change_id: Any) -> EvolvXSIAdminChange:
    expire_old(db)
    c = _get(db, change_id)
    if c.state != "pending":
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, f"A change that is {c.state} cannot be declined.")
    if c.proposed_by_id == approver.id:
        raise EvolvXSIError(EvolvXSIErrorCode.INSUFFICIENT_PERMISSIONS, "You proposed this change; cancel it instead.")
    c.state, c.decided_at, c.decided_by_email = "declined", _now(), approver.email
    db.commit()
    _audit_decision(approver, c, f"Declined: {c.summary}", AuditOutcome.DENIED)
    return c


def cancel(db: Session, user: User, change_id: Any) -> EvolvXSIAdminChange:
    c = _get(db, change_id)
    if c.state != "pending":
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, f"A change that is {c.state} cannot be cancelled.")
    if c.proposed_by_id != user.id:
        raise EvolvXSIError(EvolvXSIErrorCode.INSUFFICIENT_PERMISSIONS, "Only the person who proposed a change can cancel it.")
    c.state, c.decided_at = "cancelled", _now()
    db.commit()
    _audit_decision(user, c, f"Cancelled by its proposer: {c.summary}", AuditOutcome.SUCCESS)
    return c
