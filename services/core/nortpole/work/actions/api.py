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

from nortpole.governance.action_binding.binding import Approval, Verdict, action_fingerprint, decide_execution
from nortpole.work.actions.autonomy import LABEL, at_least, effective_tier
from nortpole.work.actions.delivery import UnsafeTarget, check_target_url, deliver, deliver_email, parse_mailto
from nortpole.work.actions.models import NortPoleAction, NortPoleActionTarget
from nortpole.auth.permissions import require_permission
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.audit import record_audit
from nortpole.governance.route_policy.policy import DATA_CLASSES, load_policy
from nortpole.work.tasks.api import _own as _own_task
from nortpole.work.tasks.export import draft_fingerprint, recheck_cited_sources, to_markdown
from nortpole.work.tasks.claims import visible_text
from nortpole.work.tasks.models import NortPoleTask
from nortpole.work.tasks.states import TaskState
from nortpole.utils.audit import AuditAction, AuditOutcome

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
    tier: Literal["read_only", "draft_only", "act_with_approval"] = "act_with_approval"
    url: str
    allowed_data_classes: list[str]
    enabled: bool = True
    require_second_approval: bool = False

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
    tier: str = "act_with_approval"
    url: str
    allowed_data_classes: list[str]
    enabled: bool
    require_second_approval: bool = False


class TargetChoice(BaseModel):
    id: int
    name: str
    tier: str = "act_with_approval"
    needs_second_approval: bool = False


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
    needs_second_approval: bool = False
    second_approved: bool = False


class SecondQueueItem(BaseModel):
    id: UUID
    target_name: str
    owner_email: str
    version: int
    fingerprint: str
    created_at: datetime.datetime


class Propose(BaseModel):
    target_id: int


class VersionOnly(BaseModel):
    version: int


class ApproveAction(BaseModel):
    version: int
    fingerprint: str


def _tview(t: NortPoleActionTarget) -> TargetView:
    return TargetView(id=t.id, name=t.name, kind=t.kind, tier=t.tier, url=t.url, allowed_data_classes=list(t.allowed_data_classes or []), enabled=t.enabled,
                      require_second_approval=bool(t.require_second_approval))


def _aview(a: NortPoleAction, db: Session) -> ActionView:
    target = db.get(NortPoleActionTarget, a.target_id) if a.target_id else None
    return ActionView.model_validate({**a.as_dict(), "needs_second_approval": bool(target and target.require_second_approval),
                                      "second_approved": a.second_approver_id is not None})


def _audit(user: User, action: AuditAction, a: NortPoleAction, summary: str, outcome: AuditOutcome = AuditOutcome.SUCCESS) -> None:
    # The payload (draft text) stays out of the audit record; the fingerprint ties it to one payload.
    record_audit(action, outcome, actor=user, summary=summary, resource_type="action", resource_id=str(a.id),
                 details={"target": a.target_name, "fingerprint": a.fingerprint})


def _own_action(db: Session, action_id: UUID, user: User) -> NortPoleAction:
    a = db.scalar(select(NortPoleAction).where(NortPoleAction.id == action_id, NortPoleAction.owner_id == user.id))
    if a is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Action not found.")
    return a


# ---- administrators: targets -------------------------------------------------

@router.get("/admin/action-targets")
def list_targets(
    _: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> list[TargetView]:
    return [_tview(t) for t in db_session.scalars(select(NortPoleActionTarget).order_by(NortPoleActionTarget.name))]


def _check_new_target(db_session: Session, body: TargetIn, *, ignore_id: int | None = None) -> None:
    try:
        _check_target(body.kind, body.url)
    except UnsafeTarget as e:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, str(e)) from e
    clash = select(NortPoleActionTarget.id).where(func.lower(NortPoleActionTarget.name) == body.name.lower())
    if ignore_id is not None:
        clash = clash.where(NortPoleActionTarget.id != ignore_id)
    if db_session.scalar(clash):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "A target with that name already exists.")


def _held(kind: str, db_session: Session, user: User, payload: dict, summary: str):  # type: ignore[no-untyped-def]
    """When the second-administrator rule covers send destinations the change is checked now and recorded as waiting."""
    from nortpole.governance.admin_changes import controls
    from nortpole.governance.admin_changes.service import pending_response, propose

    if not controls.required(kind):
        return None
    return pending_response(propose(db_session, user, kind, payload, 0, summary))


def apply_create_target(body: TargetIn, db_session: Session, user: User | None, *, approver_email: str | None = None) -> TargetView:
    _check_new_target(db_session, body)
    t = NortPoleActionTarget(name=body.name, kind=body.kind, tier=body.tier, url=body.url, allowed_data_classes=body.allowed_data_classes, enabled=body.enabled,
                           require_second_approval=body.require_second_approval)
    db_session.add(t)
    db_session.commit()
    record_audit(AuditAction.ACTION_TARGET_CHANGE, AuditOutcome.SUCCESS, actor=user,
                 summary=f"Registered action target {t.name} (tier: {t.tier}; second approver: {'required' if t.require_second_approval else 'not required'}; classes: {', '.join(t.allowed_data_classes) or 'none'})"
                 + (f" (second administrator {approver_email})" if approver_email else ""),
                 resource_type="action_target", resource_id=t.id)
    return _tview(t)


@router.post("/admin/action-targets")
def create_target(
    body: TargetIn,
    user: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> TargetView:
    _check_new_target(db_session, body)
    held = _held("send_target_create", db_session, user, body.model_dump(), f"Register send destination {body.name}")
    if held is not None:
        return held  # type: ignore[return-value]
    return apply_create_target(body, db_session, user)


def apply_update_target(target_id: int, body: TargetIn, db_session: Session, user: User | None, *, approver_email: str | None = None) -> TargetView:
    t = db_session.get(NortPoleActionTarget, target_id)
    if t is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Target not found.")
    _check_new_target(db_session, body, ignore_id=target_id)
    t.name, t.kind, t.tier, t.url, t.allowed_data_classes, t.enabled = body.name, body.kind, body.tier, body.url, body.allowed_data_classes, body.enabled
    t.require_second_approval = body.require_second_approval
    db_session.commit()
    record_audit(AuditAction.ACTION_TARGET_CHANGE, AuditOutcome.SUCCESS, actor=user,
                 summary=f"Changed action target {t.name} (tier: {t.tier}; second approver: {'required' if t.require_second_approval else 'not required'}; enabled: {t.enabled}; classes: {', '.join(t.allowed_data_classes) or 'none'})"
                 + (f" (second administrator {approver_email})" if approver_email else ""),
                 resource_type="action_target", resource_id=t.id)
    return _tview(t)


@router.patch("/admin/action-targets/{target_id}")
def update_target(
    target_id: int, body: TargetIn,
    user: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> TargetView:
    t = db_session.get(NortPoleActionTarget, target_id)
    if t is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Target not found.")
    _check_new_target(db_session, body, ignore_id=target_id)
    held = _held("send_target_update", db_session, user, {"target_id": target_id, **body.model_dump()}, f"Change send destination {t.name}")
    if held is not None:
        return held  # type: ignore[return-value]
    return apply_update_target(target_id, body, db_session, user)


def apply_destination_change(kind: str, payload: dict, db_session: Session, proposer: User | None, *, approver_email: str) -> None:
    """Run a held destination change as the second administrator approved it. Raises if it is no longer valid."""
    if kind == "send_target_create":
        apply_create_target(TargetIn(**payload), db_session, proposer, approver_email=approver_email)
    elif kind == "send_target_update":
        data = dict(payload)
        apply_update_target(int(data.pop("target_id")), TargetIn(**data), db_session, proposer, approver_email=approver_email)
    else:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Unknown kind of change.")


# ---- owners ------------------------------------------------------------------

@router.get("/action-targets")
def choose_targets(
    _: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[TargetChoice]:
    """The targets an owner may pick from. URLs are not shown."""
    rows = db_session.scalars(select(NortPoleActionTarget).where(NortPoleActionTarget.enabled.is_(True)).order_by(NortPoleActionTarget.name))
    return [TargetChoice(id=t.id, name=t.name, tier=t.tier, needs_second_approval=bool(t.require_second_approval)) for t in rows]


def _payload_from(task: NortPoleTask) -> dict:
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
    rows = db_session.scalars(select(NortPoleAction).where(NortPoleAction.task_id == task_id, NortPoleAction.owner_id == user.id)
                              .order_by(NortPoleAction.created_at.desc()))
    return [_aview(a, db_session) for a in rows]


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
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Only an approved draft can be sent. Approve the draft first.")
    target = db_session.get(NortPoleActionTarget, body.target_id)
    if target is None or not target.enabled:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Target not found.")
    tier = effective_tier(db_session, target.tier, task.pack_id, task.pack_version)
    if not at_least(tier, "draft_only"):
        record_audit(AuditAction.ACTION_PROPOSE, AuditOutcome.DENIED, actor=user, resource_type="task", resource_id=str(task.id),
                     summary=f"Proposal to {target.name} refused: {LABEL[tier]}")
        raise NortPoleError(NortPoleErrorCode.POLICY_BLOCKED, f"Nothing can be proposed to {target.name}: it is {LABEL[tier]}.")
    payload = _payload_from(task)
    a = NortPoleAction(
        task_id=task.id, owner_id=user.id, target_id=target.id, target_name=target.name, payload=payload,
        fingerprint=action_fingerprint(ACTION_NAME, target.name, payload), state="proposed", version=1,
    )
    db_session.add(a)
    db_session.commit()
    _audit(user, AuditAction.ACTION_PROPOSE, a, f"Proposed sending a draft to {target.name}")
    return _aview(a, db_session)


SECOND = "awaiting_second"  # the owner approved; a different person must approve the same payload before it can be sent


def _needs_second(db: Session, a: NortPoleAction) -> bool:
    target = db.get(NortPoleActionTarget, a.target_id) if a.target_id else None
    return bool(target and target.require_second_approval)


def _move(db: Session, a: NortPoleAction, user: User, version: int, expect: set[str], new_state: str, **values: object) -> NortPoleAction:
    if a.state not in expect:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, f"An action that is {a.state} cannot do that.")
    if a.version != version:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This action changed since you opened it. Reload and try again.")
    r = db.execute(
        update(NortPoleAction)
        .where(NortPoleAction.id == a.id, NortPoleAction.owner_id == user.id, NortPoleAction.state == a.state, NortPoleAction.version == version)
        .values(state=new_state, version=NortPoleAction.version + 1, updated_at=func.now(), **values)
        .execution_options(synchronize_session=False)
    )
    if r.rowcount != 1:
        db.rollback()
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This action changed since you opened it. Reload and try again.")
    db.commit()
    db.expire_all()
    return _own_action(db, a.id, user)


def _require_act(db: Session, user: User, a: NortPoleAction) -> None:
    """Approving and sending need the full tier, read now (not when proposed)."""
    target = db.get(NortPoleActionTarget, a.target_id) if a.target_id else None
    task = _own_task(db, a.task_id, user)
    tier = effective_tier(db, target.tier if target else "read_only", task.pack_id, task.pack_version)
    if not at_least(tier, "act_with_approval"):
        _audit(user, AuditAction.ACTION_APPROVE, a, f"Approval to {a.target_name} refused: {LABEL[tier]}", AuditOutcome.DENIED)
        raise NortPoleError(NortPoleErrorCode.POLICY_BLOCKED, f"This cannot be approved or sent: {a.target_name} is {LABEL[tier]}.")


@router.post("/actions/{action_id}/approve")
def approve_action(
    action_id: UUID, body: ApproveAction,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ActionView:
    """Approve exactly this payload. A changed payload has a different fingerprint."""
    a = _own_action(db_session, action_id, user)
    if body.fingerprint != a.fingerprint or a.fingerprint != action_fingerprint(ACTION_NAME, a.target_name, a.payload):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "What will be sent changed since you read it. Reload and review it again.")
    _require_act(db_session, user, a)
    if _needs_second(db_session, a):
        # The owner's approval is recorded; the send waits for a different person. The approval lifetime starts at the second approval.
        a = _move(db_session, a, user, body.version, {"proposed"}, SECOND)
        _audit(user, AuditAction.ACTION_APPROVE, a, f"Approved by the owner; sending to {a.target_name} now waits for a second approver")
        return _aview(a, db_session)
    a = _move(db_session, a, user, body.version, {"proposed"}, "approved", approved_at=func.now())
    _audit(user, AuditAction.ACTION_APPROVE, a, f"Approved sending to {a.target_name}")
    return _aview(a, db_session)


@router.post("/actions/{action_id}/cancel")
def cancel_action(
    action_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ActionView:
    a = _own_action(db_session, action_id, user)
    return _aview(_move(db_session, a, user, body.version, {"proposed", SECOND, "approved", "failed"}, "cancelled"), db_session)


def _refuse(db: Session, user: User, a: NortPoleAction, message: str, summary: str) -> None:
    _audit(user, AuditAction.ACTION_EXECUTE, a, summary, AuditOutcome.DENIED)
    raise NortPoleError(NortPoleErrorCode.INSUFFICIENT_PERMISSIONS, message)


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
    target = db_session.get(NortPoleActionTarget, a.target_id) if a.target_id else None
    task = _own_task(db_session, a.task_id, user)

    _require_act(db_session, user, a)
    if a.state == SECOND:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This is waiting for a second person to approve it.")
    if _needs_second(db_session, a) and (a.second_approver_id is None or a.second_approver_id == a.owner_id):
        # Read now, not when it was approved: a destination switched to need a second approver stops older approvals too.
        _refuse(db_session, user, a, f"{a.target_name} needs a second person to approve before anything is sent.",
                f"Send refused: a second approver is required for {a.target_name} and none approved")
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
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The approval has expired. Cancel and propose the action again.")
    if decision.verdict is not Verdict.ALLOWED and not (a.state == "failed" and decision.verdict is Verdict.ALREADY_USED):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This action is not approved to send.")
    if recheck_cited_sources(db_session, user, task.draft_sources).withheld:
        _refuse(db_session, user, a, "You can no longer open a source this draft cites, so it cannot be sent.",
                "Send withheld: a cited source is no longer open to the owner")
    key = a.idempotency_key or decision.idempotency_key
    if a.state not in ("approved", "failed"):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, f"An action that is {a.state} cannot be sent.")
    a = _move(db_session, a, user, body.version, {"approved", "failed"}, "executing", idempotency_key=key, attempts=NortPoleAction.attempts + 1)
    send = deliver_email if target.kind == "email" else deliver  # type: ignore[union-attr]
    result = send(target.url, a.payload, key)  # type: ignore[union-attr]
    a = _move(
        db_session, a, user, a.version, {"executing"}, "succeeded" if result.ok else "failed",
        result_status=result.status, error=result.error, executed_at=func.now() if result.ok else None,
    )
    _audit(user, AuditAction.ACTION_EXECUTE, a,
           f"Sent to {a.target_name}" if result.ok else f"Send to {a.target_name} failed",
           AuditOutcome.SUCCESS if result.ok else AuditOutcome.FAILURE)
    return _aview(a, db_session)


# ---- second approver ---------------------------------------------------------
# A destination can require a second person to approve the same payload. The second person is an administrator who is
# not the owner and who can open every source the draft cites (so approving never shows them what they may not read).
# Opening the draft for review is itself recorded in the audit log, because it shows them the owner's work.

def _action_by_id(db: Session, action_id: UUID) -> NortPoleAction:
    a = db.get(NortPoleAction, action_id)
    if a is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Action not found.")
    return a


def _second_checks(db: Session, user: User, a: NortPoleAction) -> NortPoleTask:
    """Everything that must hold before this person may read or approve. Refusals are audited."""
    def refuse(message: str, summary: str, code: NortPoleErrorCode = NortPoleErrorCode.INSUFFICIENT_PERMISSIONS) -> None:
        _audit(user, AuditAction.ACTION_APPROVE, a, summary, AuditOutcome.DENIED)
        raise NortPoleError(code, message)

    if a.owner_id == user.id:
        refuse("A second approval has to come from a different person than the one who proposed this.",
               "Second approval refused: the approver is the owner")
    if a.state != SECOND:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, f"An action that is {a.state} is not waiting for a second approval.")
    target = db.get(NortPoleActionTarget, a.target_id) if a.target_id else None
    task = db.get(NortPoleTask, a.task_id)
    if task is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Action not found.")
    tier = effective_tier(db, target.tier if target else "read_only", task.pack_id, task.pack_version)
    if not at_least(tier, "act_with_approval"):
        refuse(f"This cannot be approved: {a.target_name} is {LABEL[tier]}.", f"Second approval refused: {LABEL[tier]}", NortPoleErrorCode.POLICY_BLOCKED)
    if recheck_cited_sources(db, user, task.draft_sources).withheld:
        refuse("You cannot open a source this draft cites, so you cannot approve sending it.",
               "Second approval refused: a cited source is not open to the approver")
    return task


@router.get("/admin/actions/awaiting-second")
def awaiting_second(
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[SecondQueueItem]:
    """Sends waiting for a second approver, not including the caller's own. No draft text: that opens only on review."""
    rows = db_session.execute(
        select(NortPoleAction, User.email).join(User, User.id == NortPoleAction.owner_id)
        .where(NortPoleAction.state == SECOND, NortPoleAction.owner_id != user.id).order_by(NortPoleAction.created_at)
    ).all()
    return [SecondQueueItem(id=a.id, target_name=a.target_name, owner_email=email, version=a.version, fingerprint=a.fingerprint,
                            created_at=a.created_at) for a, email in rows]


@router.post("/admin/actions/{action_id}/second-review")
def second_review(
    action_id: UUID,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ActionView:
    """Open what would be sent. Allowed only to someone who may approve it; the opening is recorded."""
    a = _action_by_id(db_session, action_id)
    _second_checks(db_session, user, a)
    _audit(user, AuditAction.ACTION_SECOND_REVIEW, a, f"Opened a draft for second approval of sending to {a.target_name}")
    return _aview(a, db_session)


def _move_second(db: Session, a: NortPoleAction, version: int, new_state: str, **values: object) -> NortPoleAction:
    if a.version != version:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This action changed since you opened it. Reload and try again.")
    r = db.execute(
        update(NortPoleAction)
        .where(NortPoleAction.id == a.id, NortPoleAction.state == SECOND, NortPoleAction.version == version)
        .values(state=new_state, version=NortPoleAction.version + 1, updated_at=func.now(), **values)
        .execution_options(synchronize_session=False)
    )
    if r.rowcount != 1:
        db.rollback()
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This action changed since you opened it. Reload and try again.")
    db.commit()
    db.expire_all()
    return _action_by_id(db, a.id)


@router.post("/admin/actions/{action_id}/second-approve")
def second_approve(
    action_id: UUID, body: ApproveAction,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ActionView:
    """Approve exactly this payload as the second person. A changed payload has a different fingerprint."""
    a = _action_by_id(db_session, action_id)
    _second_checks(db_session, user, a)
    if body.fingerprint != a.fingerprint or a.fingerprint != action_fingerprint(ACTION_NAME, a.target_name, a.payload):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "What will be sent changed since you read it. Reload and review it again.")
    a = _move_second(db_session, a, body.version, "approved", approved_at=func.now(), second_approver_id=user.id, second_approved_at=func.now())
    _audit(user, AuditAction.ACTION_APPROVE, a, f"Second approval for sending to {a.target_name}")
    return _aview(a, db_session)


@router.post("/admin/actions/{action_id}/second-decline")
def second_decline(
    action_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ActionView:
    """Decline to approve. The action is cancelled; the owner can propose it again."""
    a = _action_by_id(db_session, action_id)
    _second_checks(db_session, user, a)
    a = _move_second(db_session, a, body.version, "cancelled")
    _audit(user, AuditAction.ACTION_APPROVE, a, f"Second approval declined for sending to {a.target_name}", AuditOutcome.DENIED)
    return _aview(a, db_session)


def _register_with_admin_changes() -> None:
    from nortpole.governance.admin_changes import controls
    from nortpole.governance.admin_changes.service import register_applier

    register_applier(controls.DESTINATION_KINDS, apply_destination_change)


_register_with_admin_changes()
