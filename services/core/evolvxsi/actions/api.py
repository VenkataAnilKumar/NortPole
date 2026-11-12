"""Action endpoints. Owners propose an action from an approved draft; the
payload is built here from that draft. They then approve that exact payload,
and execute it. Administrators register the targets."""

from __future__ import annotations

import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from evolvxsi.action_binding.binding import Approval, Verdict, action_fingerprint, decide_execution
from evolvxsi.actions.delivery import UnsafeTarget, check_target_url, deliver, deliver_email, parse_mailto
from evolvxsi.actions.models import EvolvXSIAction, EvolvXSIActionTarget
from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.route_policy.audit import record_audit
from evolvxsi.route_policy.policy import DATA_CLASSES, load_policy
from evolvxsi.tasks.api import _own as _own_task
from evolvxsi.tasks.export import draft_fingerprint, recheck_cited_sources, to_markdown
from evolvxsi.tasks.claims import visible_text
from evolvxsi.tasks.models import EvolvXSITask
from evolvxsi.tasks.states import TaskState
from evolvxsi.utils.audit import AuditAction, AuditOutcome

router = APIRouter()
ACTION_NAME = "send_draft"
APPROVAL_LIFETIME = datetime.timedelta(minutes=30)


def _check_target(kind: str, url: str) -> None:
    if kind == "email":
        parse_mailto(url)
    else:
        check_target_url(url)


class TargetIn(BaseModel):
    name: str
    kind: Literal["webhook", "email"] = "webhook"
    url: str
    allowed_data_classes: list[str]
    enabled: bool = True

    @field_validator("allowed_data_classes")
    @classmethod
    def _classes(cls, v: list[str]) -> list[str]:
        bad = [c for c in v if c not in DATA_CLASSES]
        if bad:
            raise ValueError(f"Unknown data class: {', '.join(bad)}")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("A target needs a name.")
        return v


class TargetView(BaseModel):
    id: int
    name: str
    kind: str = "webhook"
    url: str
    allowed_data_classes: list[str]
    enabled: bool


class TargetChoice(BaseModel):
    id: int
    name: str


class ActionView(BaseModel):
    id: UUID
    task_id: UUID
    target_name: str
    state: str
    version: int
    fingerprint: str
    payload: dict
    approved_at: datetime.datetime | None
    attempts: int
    result_status: int | None
    error: str | None
    executed_at: datetime.datetime | None


class Propose(BaseModel):
    target_id: int


class VersionOnly(BaseModel):
    version: int


class ApproveAction(BaseModel):
    version: int
    fingerprint: str


def _tview(t: EvolvXSIActionTarget) -> TargetView:
    return TargetView(id=t.id, name=t.name, kind=t.kind, url=t.url, allowed_data_classes=list(t.allowed_data_classes or []), enabled=t.enabled)


def _aview(a: EvolvXSIAction) -> ActionView:
    return ActionView.model_validate(a.as_dict())


def _audit(user: User, action: AuditAction, a: EvolvXSIAction, summary: str, outcome: AuditOutcome = AuditOutcome.SUCCESS) -> None:
    # The payload (draft text) stays out of the audit record; the fingerprint ties it to one payload.
    record_audit(action, outcome, actor=user, summary=summary, resource_type="action", resource_id=str(a.id),
                 details={"target": a.target_name, "fingerprint": a.fingerprint})


def _own_action(db: Session, action_id: UUID, user: User) -> EvolvXSIAction:
    a = db.scalar(select(EvolvXSIAction).where(EvolvXSIAction.id == action_id, EvolvXSIAction.owner_id == user.id))
    if a is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Action not found.")
    return a


# ---- administrators: targets -------------------------------------------------

@router.get("/admin/action-targets")
def list_targets(
    _: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> list[TargetView]:
    return [_tview(t) for t in db_session.scalars(select(EvolvXSIActionTarget).order_by(EvolvXSIActionTarget.name))]


@router.post("/admin/action-targets")
def create_target(
    body: TargetIn,
    user: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> TargetView:
    try:
        _check_target(body.kind, body.url)
    except UnsafeTarget as e:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, str(e)) from e
    if db_session.scalar(select(EvolvXSIActionTarget.id).where(func.lower(EvolvXSIActionTarget.name) == body.name.lower())):
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "A target with that name already exists.")
    t = EvolvXSIActionTarget(name=body.name, kind=body.kind, url=body.url, allowed_data_classes=body.allowed_data_classes, enabled=body.enabled)
    db_session.add(t)
    db_session.commit()
    record_audit(AuditAction.ACTION_TARGET_CHANGE, AuditOutcome.SUCCESS, actor=user,
                 summary=f"Registered action target {t.name} (classes: {', '.join(t.allowed_data_classes) or 'none'})",
                 resource_type="action_target", resource_id=t.id)
    return _tview(t)


@router.patch("/admin/action-targets/{target_id}")
def update_target(
    target_id: int, body: TargetIn,
    user: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> TargetView:
    t = db_session.get(EvolvXSIActionTarget, target_id)
    if t is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Target not found.")
    try:
        _check_target(body.kind, body.url)
    except UnsafeTarget as e:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, str(e)) from e
    t.name, t.kind, t.url, t.allowed_data_classes, t.enabled = body.name, body.kind, body.url, body.allowed_data_classes, body.enabled
    db_session.commit()
    record_audit(AuditAction.ACTION_TARGET_CHANGE, AuditOutcome.SUCCESS, actor=user,
                 summary=f"Changed action target {t.name} (enabled: {t.enabled}; classes: {', '.join(t.allowed_data_classes) or 'none'})",
                 resource_type="action_target", resource_id=t.id)
    return _tview(t)


# ---- owners ------------------------------------------------------------------

@router.get("/action-targets")
def choose_targets(
    _: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[TargetChoice]:
    """The targets an owner may pick from. URLs are not shown."""
    rows = db_session.scalars(select(EvolvXSIActionTarget).where(EvolvXSIActionTarget.enabled.is_(True)).order_by(EvolvXSIActionTarget.name))
    return [TargetChoice(id=t.id, name=t.name) for t in rows]


def _payload_from(task: EvolvXSITask) -> dict:
    text = visible_text(task.draft_claims, label_unsupported=True) if task.draft_claims else (task.draft_text or "")
    return {
        "title": task.title,
        "markdown": to_markdown(task.title, text, task.draft_sources),
        "task_id": str(task.id),
    }


@router.get("/tasks/{task_id}/actions")
def list_actions(
    task_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[ActionView]:
    _own_task(db_session, task_id, user)
    rows = db_session.scalars(select(EvolvXSIAction).where(EvolvXSIAction.task_id == task_id, EvolvXSIAction.owner_id == user.id)
                              .order_by(EvolvXSIAction.created_at.desc()))
    return [_aview(a) for a in rows]


@router.post("/tasks/{task_id}/actions")
def propose_action(
    task_id: UUID, body: Propose,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ActionView:
    """Propose sending the approved draft to a registered target. The payload is
    built from the draft here; nothing is sent until the owner approves it."""
    task = _own_task(db_session, task_id, user)
    if TaskState(task.state) is not TaskState.APPROVED or task.approved_hash != draft_fingerprint(
        task.draft_text or "", task.draft_sources, task.draft_claims
    ):
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Only an approved draft can be sent. Approve the draft first.")
    target = db_session.get(EvolvXSIActionTarget, body.target_id)
    if target is None or not target.enabled:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Target not found.")
    payload = _payload_from(task)
    a = EvolvXSIAction(
        task_id=task.id, owner_id=user.id, target_id=target.id, target_name=target.name, payload=payload,
        fingerprint=action_fingerprint(ACTION_NAME, target.name, payload), state="proposed", version=1,
    )
    db_session.add(a)
    db_session.commit()
    _audit(user, AuditAction.ACTION_PROPOSE, a, f"Proposed sending a draft to {target.name}")
    return _aview(a)


def _move(db: Session, a: EvolvXSIAction, user: User, version: int, expect: set[str], new_state: str, **values: object) -> EvolvXSIAction:
    if a.state not in expect:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, f"An action that is {a.state} cannot do that.")
    if a.version != version:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This action changed since you opened it. Reload and try again.")
    r = db.execute(
        update(EvolvXSIAction)
        .where(EvolvXSIAction.id == a.id, EvolvXSIAction.owner_id == user.id, EvolvXSIAction.state == a.state, EvolvXSIAction.version == version)
        .values(state=new_state, version=EvolvXSIAction.version + 1, updated_at=func.now(), **values)
        .execution_options(synchronize_session=False)
    )
    if r.rowcount != 1:
        db.rollback()
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This action changed since you opened it. Reload and try again.")
    db.commit()
    db.expire_all()
    return _own_action(db, a.id, user)


@router.post("/actions/{action_id}/approve")
def approve_action(
    action_id: UUID, body: ApproveAction,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ActionView:
    """Approve exactly this payload. A changed payload has a different fingerprint."""
    a = _own_action(db_session, action_id, user)
    if body.fingerprint != a.fingerprint or a.fingerprint != action_fingerprint(ACTION_NAME, a.target_name, a.payload):
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "What will be sent changed since you read it. Reload and review it again.")
    a = _move(db_session, a, user, body.version, {"proposed"}, "approved", approved_at=func.now())
    _audit(user, AuditAction.ACTION_APPROVE, a, f"Approved sending to {a.target_name}")
    return _aview(a)


@router.post("/actions/{action_id}/cancel")
def cancel_action(
    action_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ActionView:
    a = _own_action(db_session, action_id, user)
    return _aview(_move(db_session, a, user, body.version, {"proposed", "approved", "failed"}, "cancelled"))


def _refuse(db: Session, user: User, a: EvolvXSIAction, message: str, summary: str) -> None:
    _audit(user, AuditAction.ACTION_EXECUTE, a, summary, AuditOutcome.DENIED)
    raise EvolvXSIError(EvolvXSIErrorCode.INSUFFICIENT_PERMISSIONS, message)


@router.post("/actions/{action_id}/execute")
def execute_action(
    action_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ActionView:
    """Send an approved action. Re-checks, at this moment: the destination is
    still enabled and allowed for the workspace's data class (policy), the owner
    can still open every cited source, and the approval is exact, unexpired and
    unused. A failed send can be retried with the same request key."""
    a = _own_action(db_session, action_id, user)
    target = db_session.get(EvolvXSIActionTarget, a.target_id) if a.target_id else None
    task = _own_task(db_session, a.task_id, user)

    data_class = load_policy().default_data_class
    policy_ok = bool(target and target.enabled and data_class in (target.allowed_data_classes or []))
    approval = Approval(
        approval_id=str(a.id), fingerprint=a.fingerprint, approver=str(user.id),
        approved_at=a.approved_at or datetime.datetime.now(datetime.timezone.utc),
        lifetime=APPROVAL_LIFETIME, used=a.state in ("executing", "succeeded"),
    ) if a.state in ("approved", "failed", "executing", "succeeded") and a.approved_at else None
    decision = decide_execution(
        action=ACTION_NAME, target=a.target_name, payload=a.payload, approval=approval, policy_allows=policy_ok,
    )
    if decision.verdict is Verdict.POLICY_BLOCKED:
        _refuse(db_session, user, a, f"Blocked by policy: this workspace's data class ({data_class}) is not allowed to go to {a.target_name}.",
                f"Blocked by policy: {data_class} to {a.target_name}")
    if decision.verdict is Verdict.EXPIRED:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "The approval has expired. Cancel and propose the action again.")
    if decision.verdict is not Verdict.ALLOWED and not (a.state == "failed" and decision.verdict is Verdict.ALREADY_USED):
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This action is not approved to send.")
    if recheck_cited_sources(db_session, user, task.draft_sources).withheld:
        _refuse(db_session, user, a, "You can no longer open a source this draft cites, so it cannot be sent.",
                "Send withheld: a cited source is no longer open to the owner")
    key = a.idempotency_key or decision.idempotency_key
    if a.state not in ("approved", "failed"):
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, f"An action that is {a.state} cannot be sent.")
    a = _move(db_session, a, user, body.version, {"approved", "failed"}, "executing", idempotency_key=key, attempts=EvolvXSIAction.attempts + 1)
    send = deliver_email if target.kind == "email" else deliver  # type: ignore[union-attr]
    result = send(target.url, a.payload, key)  # type: ignore[union-attr]
    a = _move(
        db_session, a, user, a.version, {"executing"}, "succeeded" if result.ok else "failed",
        result_status=result.status, error=result.error, executed_at=func.now() if result.ok else None,
    )
    _audit(user, AuditAction.ACTION_EXECUTE, a,
           f"Sent to {a.target_name}" if result.ok else f"Send to {a.target_name} failed",
           AuditOutcome.SUCCESS if result.ok else AuditOutcome.FAILURE)
    return _aview(a)
