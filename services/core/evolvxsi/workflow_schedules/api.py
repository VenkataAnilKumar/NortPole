"""Scheduled workflows. People create, change, pause, resume and delete their own schedules and read each run's
history. Administrators turn scheduling on, choose who may use it, see every schedule (never its request text) and
can pause any. A run only ever drafts a plan for its owner."""

from __future__ import annotations

import datetime
import random
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.knowledge_access.groups import group_names_for_user
from evolvxsi.route_policy.audit import record_audit
from evolvxsi.tasks.models import EvolvXSITask
from evolvxsi.utils.audit import AuditAction, AuditOutcome
from evolvxsi.workflow_schedules import cadence, controls, runner
from evolvxsi.workflow_schedules.models import EvolvXSIWorkflowRun, EvolvXSIWorkflowSchedule

router = APIRouter()
MAX_TEXT = 8000


class When(BaseModel):
    cadence: str
    at_time: str = Field(max_length=5)
    timezone: str = Field(max_length=64)
    weekday: int | None = None
    month_day: int | None = None
    run_on: datetime.date | None = None


class NewSchedule(When):
    name: str = Field(min_length=1, max_length=200)
    # One source: a pack template, one of the person's drafts, or their own text.
    pack_id: str | None = None
    pack_template: str | None = None
    task_id: UUID | None = None
    title: str | None = Field(default=None, max_length=300)
    request: str | None = Field(default=None, max_length=MAX_TEXT)
    desired_output: str = Field(default="", max_length=MAX_TEXT)


class EditSchedule(When):
    version: int
    name: str = Field(min_length=1, max_length=200)


class VersionOnly(BaseModel):
    version: int


class RunView(BaseModel):
    id: UUID
    fired_at: datetime.datetime
    outcome: str
    reason: str | None
    task_id: UUID | None
    task_state: str | None  # the draft's state now, so the history shows how far it got
    route_kind: str | None
    input_tokens: int
    output_tokens: int


class ScheduleView(BaseModel):
    id: UUID
    name: str
    title: str
    pack_id: str | None
    pack_template: str | None
    cadence: str
    at_time: str
    timezone: str
    weekday: int | None
    month_day: int | None
    run_on: datetime.date | None
    when: str
    next_run_at: datetime.datetime | None
    state: str
    pause_reason: str | None
    pause_text: str | None
    unaccepted_streak: int
    last_run: RunView | None
    version: int


class MySchedules(BaseModel):
    schedules: list[ScheduleView]
    scheduling_allowed: bool
    max_per_person: int


def _run_view(db: Session, r: EvolvXSIWorkflowRun) -> RunView:
    t = db.get(EvolvXSITask, r.task_id) if r.task_id else None
    return RunView(id=r.id, fired_at=r.fired_at, outcome=r.outcome, reason=r.reason, task_id=r.task_id,
                   task_state=t.state if t else None, route_kind=r.route_kind, input_tokens=r.input_tokens, output_tokens=r.output_tokens)


def _view(db: Session, s: EvolvXSIWorkflowSchedule) -> ScheduleView:
    last = db.scalar(select(EvolvXSIWorkflowRun).where(EvolvXSIWorkflowRun.schedule_id == s.id).order_by(EvolvXSIWorkflowRun.fired_at.desc()).limit(1))
    return ScheduleView(
        id=s.id, name=s.name, title=s.title, pack_id=s.pack_id, pack_template=s.pack_template, cadence=s.cadence, at_time=s.at_time,
        timezone=s.timezone, weekday=s.weekday, month_day=s.month_day, run_on=s.run_on,
        when=cadence.describe(s.cadence, s.at_time, s.timezone, s.weekday, s.month_day, s.run_on),
        next_run_at=s.next_run_at, state=s.state, pause_reason=s.pause_reason,
        pause_text=runner.PAUSE_TEXT.get(s.pause_reason or "") if s.state == "paused" else None,
        unaccepted_streak=s.unaccepted_streak, last_run=_run_view(db, last) if last else None, version=s.version)


def _check_when(w: When) -> None:
    try:
        cadence.validate(w.cadence, w.at_time, w.timezone, w.weekday, w.month_day, w.run_on)
    except cadence.CadenceError as e:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, str(e)) from e


def _allowed(db: Session, user: User) -> bool:
    return controls.allowed_for(controls.load(), group_names_for_user(db, user.id))


def _own(db: Session, schedule_id: UUID, user: User) -> EvolvXSIWorkflowSchedule:
    s = db.get(EvolvXSIWorkflowSchedule, schedule_id)
    if s is None or s.owner_id != user.id:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Schedule not found.")
    return s


def _audit(action: AuditAction, user: User | None, s: EvolvXSIWorkflowSchedule, summary: str, **details: object) -> None:
    # The name is the person's own text; it stays out of the audit record like a draft's title.
    record_audit(action, AuditOutcome.SUCCESS, actor=user, summary=summary, details=dict(details) or None,
                 resource_type="workflow_schedule", resource_id=str(s.id))


def _set_when(s: EvolvXSIWorkflowSchedule, w: When, now: datetime.datetime) -> None:
    s.cadence, s.at_time, s.timezone, s.weekday, s.month_day, s.run_on = w.cadence, w.at_time, w.timezone, w.weekday, w.month_day, w.run_on
    if s.state == "active":
        s.next_run_at = runner.compute_next(s, now)
        if s.next_run_at is None:
            raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "That time has already passed.")


@router.get("/workflow-schedules")
def list_mine(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MySchedules:
    rows = db_session.scalars(select(EvolvXSIWorkflowSchedule).where(EvolvXSIWorkflowSchedule.owner_id == user.id)
                              .order_by(EvolvXSIWorkflowSchedule.created_at.desc()))
    return MySchedules(schedules=[_view(db_session, s) for s in rows], scheduling_allowed=_allowed(db_session, user),
                       max_per_person=controls.load().max_per_person)


@router.post("/workflow-schedules")
def create_schedule(
    body: NewSchedule,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ScheduleView:
    if not _allowed(db_session, user):
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT,
                            "Scheduling is not turned on for you. An administrator decides who may schedule workflows.")
    _check_when(body)
    live = db_session.scalar(select(func.count()).select_from(EvolvXSIWorkflowSchedule)
                             .where(EvolvXSIWorkflowSchedule.owner_id == user.id, EvolvXSIWorkflowSchedule.state != "ended")) or 0
    if live >= controls.load().max_per_person:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "You have the most schedules allowed. Delete one first.")
    if body.task_id is not None:
        t = db_session.scalar(select(EvolvXSITask).where(EvolvXSITask.id == body.task_id, EvolvXSITask.owner_id == user.id))
        if t is None:
            raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Draft not found.")
        pack_id, template, title, request, desired = t.pack_id, t.pack_template, t.title, t.request, t.desired_output
    elif body.pack_id and body.pack_template:
        from evolvxsi.packs.api import _active_versions

        v = next((x for x in _active_versions(db_session) if x.pack_id == body.pack_id), None)
        t = next((x for x in v.manifest["templates"] if x["id"] == body.pack_template), None) if v else None
        if t is None:
            raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Workflow not found.")
        pack_id, template, title, request, desired = body.pack_id, body.pack_template, t["title"], t["request"], t.get("desired_output", "")
    elif body.title and body.request:
        pack_id, template, title, request, desired = None, None, body.title, body.request, body.desired_output
    else:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "Choose a workflow, one of your drafts, or write the request.")
    s = EvolvXSIWorkflowSchedule(owner_id=user.id, name=body.name.strip(), pack_id=pack_id, pack_template=template, title=title,
                                 request=request, desired_output=desired or "", spread_minutes=random.randint(0, 4),  # noqa: S311
                                 state="active", shared_with_groups=[])
    _set_when(s, body, datetime.datetime.now(datetime.timezone.utc))
    db_session.add(s)
    db_session.commit()
    _audit(AuditAction.SCHEDULE_CHANGE, user, s, "Created a schedule", change="create", cadence=s.cadence)
    return _view(db_session, s)


@router.patch("/workflow-schedules/{schedule_id}")
def edit_schedule(
    schedule_id: UUID, body: EditSchedule,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ScheduleView:
    s = _own(db_session, schedule_id, user)
    if s.version != body.version:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This schedule changed since you opened it. Reload and try again.")
    _check_when(body)
    s.name = body.name.strip()
    _set_when(s, body, datetime.datetime.now(datetime.timezone.utc))
    s.version += 1
    db_session.commit()
    _audit(AuditAction.SCHEDULE_CHANGE, user, s, "Changed a schedule", change="edit", cadence=s.cadence)
    return _view(db_session, s)


@router.post("/workflow-schedules/{schedule_id}/pause")
def pause_schedule(
    schedule_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ScheduleView:
    s = _own(db_session, schedule_id, user)
    if s.state != "active" or s.version != body.version:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Only an active schedule can be paused. Reload and try again.")
    runner.pause(db_session, s, "owner", actor=user, notify=False)
    return _view(db_session, s)


@router.post("/workflow-schedules/{schedule_id}/resume")
def resume_schedule(
    schedule_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ScheduleView:
    s = _own(db_session, schedule_id, user)
    if s.state != "paused" or s.version != body.version:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Only a paused schedule can be resumed. Reload and try again.")
    if not _allowed(db_session, user):
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Scheduling is not turned on for you. An administrator decides who may schedule workflows.")
    nxt = runner.compute_next(s, datetime.datetime.now(datetime.timezone.utc))
    if nxt is None:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Its time has passed. Edit the date first.")
    s.state, s.pause_reason, s.next_run_at = "active", None, nxt
    s.unaccepted_streak = s.skip_streak = 0
    s.version += 1
    db_session.commit()
    _audit(AuditAction.SCHEDULE_STATE, user, s, "Schedule resumed", state="active")
    return _view(db_session, s)


@router.delete("/workflow-schedules/{schedule_id}")
def delete_schedule(
    schedule_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    s = _own(db_session, schedule_id, user)
    _audit(AuditAction.SCHEDULE_CHANGE, user, s, "Deleted a schedule", change="delete")
    db_session.delete(s)  # its runs go with it; the drafts it made stay, unlinked
    db_session.commit()


@router.get("/workflow-schedules/{schedule_id}/runs")
def list_runs(
    schedule_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[RunView]:
    s = _own(db_session, schedule_id, user)
    runs = db_session.scalars(select(EvolvXSIWorkflowRun).where(EvolvXSIWorkflowRun.schedule_id == s.id)
                              .order_by(EvolvXSIWorkflowRun.fired_at.desc()).limit(50))
    return [_run_view(db_session, r) for r in runs]


# ---- administrators ----

class ControlsUpdate(BaseModel):
    enabled: bool
    groups: list[str] = Field(default_factory=list, max_length=100)
    max_per_person: int = Field(default=10, ge=1, le=50)


class AdminScheduleView(BaseModel):
    id: UUID
    owner_email: str
    when: str
    state: str
    pause_reason: str | None
    next_run_at: datetime.datetime | None
    last_outcome: str | None
    last_fired_at: datetime.datetime | None


@router.get("/admin/workflow-schedules/controls")
def get_controls(_: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> controls.ScheduleControls:
    return controls.load()


@router.put("/admin/workflow-schedules/controls")
def put_controls(
    body: ControlsUpdate,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> controls.ScheduleControls:
    old = controls.load()
    new = controls.ScheduleControls(version=old.version + 1, enabled=body.enabled,
                                    groups=sorted({g.strip() for g in body.groups if g.strip()}), max_per_person=body.max_per_person)
    controls.save(new)
    record_audit(AuditAction.SCHEDULE_CONTROLS, AuditOutcome.SUCCESS, actor=user,
                 summary=f"Scheduling {'on' if new.enabled else 'off'}" + (f" for {len(new.groups)} group(s)" if new.enabled and new.groups else ""),
                 details={"enabled": new.enabled, "groups": new.groups, "max_per_person": new.max_per_person},
                 resource_type="schedule_controls", resource_id="workspace")
    return new


@router.get("/admin/workflow-schedules")
def list_all(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[AdminScheduleView]:
    out = []
    rows = db_session.execute(select(EvolvXSIWorkflowSchedule, User.email).join(User, User.id == EvolvXSIWorkflowSchedule.owner_id)
                              .order_by(EvolvXSIWorkflowSchedule.created_at.desc()).limit(500)).all()
    for s, email in rows:
        last = db_session.scalar(select(EvolvXSIWorkflowRun.outcome).where(EvolvXSIWorkflowRun.schedule_id == s.id)
                                 .order_by(EvolvXSIWorkflowRun.fired_at.desc()).limit(1))
        out.append(AdminScheduleView(id=s.id, owner_email=email, when=cadence.describe(s.cadence, s.at_time, s.timezone, s.weekday, s.month_day, s.run_on),
                                     state=s.state, pause_reason=s.pause_reason, next_run_at=s.next_run_at, last_outcome=last, last_fired_at=s.last_fired_at))
    return out


@router.post("/admin/workflow-schedules/{schedule_id}/pause")
def admin_pause(
    schedule_id: UUID,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> AdminScheduleView:
    s = db_session.get(EvolvXSIWorkflowSchedule, schedule_id)
    if s is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Schedule not found.")
    if s.state != "active":
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Only an active schedule can be paused.")
    runner.pause(db_session, s, "admin", actor=user)
    return next(v for v in list_all(_=user, db_session=db_session) if v.id == s.id)


@router.post("/admin/workflow-schedules/run-due")
def run_due_now(_: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> dict[str, int]:
    """Fire what is due now, as the background worker does every five minutes; for deployments without the worker."""
    return {"fired": runner.run_due()}
