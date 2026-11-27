"""Manage scheduled workflows and their run history, including on-demand runs by schedule owners."""

from __future__ import annotations

import datetime
import random
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.knowledge.knowledge_access.groups import group_names_for_user
from nortpole.governance.route_policy.audit import record_audit
from nortpole.work.tasks.models import NortPoleTask
from nortpole.utils.audit import AuditAction, AuditOutcome
from nortpole.work.workflow_schedules import cadence, controls, runner, source_events
from nortpole.work.workflow_schedules.expense_review import RECEIPT_REVIEW_REQUEST, validate_inputs
from nortpole.work.workflow_schedules.models import (
    ExpenseReviewInputs,
    NortPoleWorkflowRun,
    NortPoleWorkflowSchedule,
    shared_schedule_clause,
)

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
    source_library_id: int | None = Field(default=None, gt=0)
    prepare_now: bool = False
    notify_plan_ready: bool = False
    notify_needs_review: bool = True
    notify_run_failed: bool = True
    notify_run_complete: bool = False
    # One source: a pack template, a personal draft, a custom request, or Expense Review.
    pack_id: str | None = None
    pack_template: str | None = None
    task_id: UUID | None = None
    expense_review: ExpenseReviewInputs | None = None
    title: str | None = Field(default=None, max_length=300)
    request: str | None = Field(default=None, max_length=MAX_TEXT)
    desired_output: str = Field(default="", max_length=MAX_TEXT)


class EditSchedule(When):
    source_library_id: int | None = Field(default=None, gt=0)
    notify_plan_ready: bool | None = None
    notify_needs_review: bool | None = None
    notify_run_failed: bool | None = None
    notify_run_complete: bool | None = None
    version: int
    name: str = Field(min_length=1, max_length=200)
    expense_review: ExpenseReviewInputs | None = None


class VersionOnly(BaseModel):
    version: int


class RunView(BaseModel):
    id: UUID
    fired_at: datetime.datetime
    outcome: str
    reason: str | None
    task_id: UUID | None
    chat_session_id: UUID | None
    task_state: str | None  # the draft's state now, so the history shows how far it got
    route_kind: str | None
    input_tokens: int
    output_tokens: int


class ScheduleView(BaseModel):
    id: UUID
    notify_plan_ready: bool
    notify_needs_review: bool
    notify_run_failed: bool
    notify_run_complete: bool
    name: str
    title: str
    pack_id: str | None
    pack_template: str | None
    expense_review: ExpenseReviewInputs | None
    source_library_id: int | None = None
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
    shared_with_groups: list[str]
    copied_from_id: UUID | None
    version: int


class MySchedules(BaseModel):
    schedules: list[ScheduleView]
    scheduling_allowed: bool
    source_events_allowed: bool = False
    max_per_person: int
    my_groups: list[str]  # the groups this person may share a schedule with


class CreatedSchedule(ScheduleView):
    initial_plan: RunView | None = None


def _run_view(db: Session, r: NortPoleWorkflowRun) -> RunView:
    t = db.get(NortPoleTask, r.task_id) if r.task_id else None
    outcome = runner.effective_outcome(r, datetime.datetime.now(datetime.timezone.utc))
    return RunView(id=r.id, fired_at=r.fired_at, outcome=outcome, reason=r.reason, task_id=r.task_id, chat_session_id=r.chat_session_id,
                   task_state=t.state if t else None, route_kind=r.route_kind, input_tokens=r.input_tokens, output_tokens=r.output_tokens)


def _view(db: Session, s: NortPoleWorkflowSchedule) -> ScheduleView:
    last = db.scalar(select(NortPoleWorkflowRun).where(NortPoleWorkflowRun.schedule_id == s.id).order_by(NortPoleWorkflowRun.fired_at.desc()).limit(1))
    return ScheduleView(
        id=s.id, name=s.name, title=s.title, notify_plan_ready=s.notify_plan_ready,
        notify_needs_review=s.notify_needs_review, notify_run_failed=s.notify_run_failed,
        notify_run_complete=s.notify_run_complete,
        pack_id=s.pack_id, pack_template=s.pack_template, expense_review=s.expense_review,
        source_library_id=s.source_library_id, cadence=s.cadence, at_time=s.at_time,
        timezone=s.timezone, weekday=s.weekday, month_day=s.month_day, run_on=s.run_on,
        when=cadence.describe(s.cadence, s.at_time, s.timezone, s.weekday, s.month_day, s.run_on),
        next_run_at=s.next_run_at, state=s.state, pause_reason=s.pause_reason,
        pause_text=runner.PAUSE_TEXT.get(s.pause_reason or "") if s.state == "paused" else None,
        unaccepted_streak=s.unaccepted_streak, last_run=_run_view(db, last) if last else None,
        shared_with_groups=list(s.shared_with_groups or []), copied_from_id=s.copied_from_id, version=s.version)


def _check_when(w: When) -> None:
    if w.cadence == "source":
        return
    try:
        cadence.validate(w.cadence, w.at_time, w.timezone, w.weekday, w.month_day, w.run_on)
    except cadence.CadenceError as e:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, str(e)) from e


def _allowed(db: Session, user: User) -> bool:
    return controls.allowed_for(controls.load(), group_names_for_user(db, user.id))


def _own(db: Session, schedule_id: UUID, user: User) -> NortPoleWorkflowSchedule:
    s = db.get(NortPoleWorkflowSchedule, schedule_id)
    if s is None or s.owner_id != user.id:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Schedule not found.")
    return s


def _audit(action: AuditAction, user: User | None, s: NortPoleWorkflowSchedule, summary: str, **details: object) -> None:
    # The name is the person's own text; it stays out of the audit record like a draft's title.
    record_audit(action, AuditOutcome.SUCCESS, actor=user, summary=summary, details=dict(details) or None,
                 resource_type="workflow_schedule", resource_id=str(s.id))


def _check_limit(db: Session, user: User, *, writing: bool = False) -> None:
    if writing:
        # Serialize the quota check and save across direct and confirmed Chat requests.
        db.execute(select(User.id).where(User.id == user.id).with_for_update(key_share=True))
    live = db.scalar(select(func.count()).select_from(NortPoleWorkflowSchedule)
                     .where(NortPoleWorkflowSchedule.owner_id == user.id, NortPoleWorkflowSchedule.state != "ended")) or 0
    if live >= controls.load().max_per_person:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "You have the most schedules allowed. Delete one first.")


def _active_template(db: Session, pack_id: str, template_id: str) -> dict | None:
    from nortpole.work.packs.api import _active_versions

    v = next((x for x in _active_versions(db) if x.pack_id == pack_id), None)
    return next((x for x in v.manifest["templates"] if x["id"] == template_id), None) if v else None


def _set_when(s: NortPoleWorkflowSchedule, w: When, now: datetime.datetime) -> None:
    s.cadence, s.at_time, s.timezone, s.weekday, s.month_day, s.run_on = w.cadence, w.at_time, w.timezone, w.weekday, w.month_day, w.run_on
    if w.cadence == "source":
        s.next_run_at = None
    elif s.state == "active":
        s.next_run_at = runner.compute_next(s, now)
        if s.next_run_at is None:
            raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "That time has already passed.")


def _check_source(db: Session, user: User, library_id: int | None) -> None:
    if not source_events.allowed(controls.load(), group_names_for_user(db, user.id)):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Knowledge triggers are turned off for this account.")
    if library_id is None:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose a Knowledge library.")
    source_events.library_for(db, user, library_id)


@router.get("/workflow-schedules")
def list_mine(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MySchedules:
    rows = db_session.scalars(select(NortPoleWorkflowSchedule).where(NortPoleWorkflowSchedule.owner_id == user.id)
                              .order_by(NortPoleWorkflowSchedule.created_at.desc()))
    config = controls.load()
    groups = group_names_for_user(db_session, user.id)
    return MySchedules(schedules=[_view(db_session, s) for s in rows],
                       scheduling_allowed=controls.allowed_for(config, groups), source_events_allowed=source_events.allowed(config, groups),
                       max_per_person=config.max_per_person, my_groups=sorted(groups))


@router.post("/workflow-schedules")
def create_schedule(
    body: NewSchedule,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> CreatedSchedule:
    if not _allowed(db_session, user):
        raise NortPoleError(NortPoleErrorCode.CONFLICT,
                            "Scheduling is not turned on for you. An administrator decides who may schedule workflows.")
    _check_when(body)
    if body.cadence == "source":
        if any((body.expense_review, body.task_id, body.pack_id, body.pack_template, body.prepare_now)):
            raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Write a request for a Knowledge-triggered workflow.")
        _check_source(db_session, user, body.source_library_id)
    elif body.source_library_id is not None:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose the Knowledge change trigger to watch a library.")
    _check_limit(db_session, user, writing=True)
    if body.expense_review is not None:
        if any((body.task_id, body.pack_id, body.pack_template, body.title, body.request)):
            raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose one workflow source.")
        validate_inputs(db_session, user, body.expense_review)
        pack_id, template, title, request, desired = None, None, "Expense Review", RECEIPT_REVIEW_REQUEST, ""
    elif body.task_id is not None:
        t = db_session.scalar(select(NortPoleTask).where(NortPoleTask.id == body.task_id, NortPoleTask.owner_id == user.id))
        if t is None:
            raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Draft not found.")
        pack_id, template, title, request, desired = t.pack_id, t.pack_template, t.title, t.request, t.desired_output
    elif body.pack_id and body.pack_template:
        t = _active_template(db_session, body.pack_id, body.pack_template)
        if t is None:
            raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Workflow not found.")
        pack_id, template, title, request, desired = body.pack_id, body.pack_template, t["title"], t["request"], t.get("desired_output", "")
    elif body.title and body.request:
        pack_id, template, title, request, desired = None, None, body.title, body.request, body.desired_output
    else:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose a workflow, one of your drafts, or write the request.")
    s = NortPoleWorkflowSchedule(owner_id=user.id, name=body.name.strip(), pack_id=pack_id, pack_template=template, title=title,
                                 request=request, desired_output=desired or "", spread_minutes=random.randint(0, 4),  # noqa: S311
                                 state="active", shared_with_groups=[], expense_review=body.expense_review,
                                 notify_plan_ready=body.notify_plan_ready and body.expense_review is None,
                                 notify_needs_review=body.notify_needs_review, notify_run_failed=body.notify_run_failed,
                                 notify_run_complete=body.notify_run_complete)
    _set_when(s, body, datetime.datetime.now(datetime.timezone.utc))
    if body.cadence == "source":
        s.source_library_id = body.source_library_id
        s.source_since = func.clock_timestamp()
    db_session.add(s)
    db_session.commit()
    _audit(AuditAction.SCHEDULE_CHANGE, user, s, "Created a schedule", change="create", cadence=s.cadence)
    initial_plan = None
    if body.prepare_now:
        # Running immediately leaves the next scheduled occurrence intact.
        try:
            run = runner.fire_one(db_session, s.id, manual_version=s.version)
            if run is not None:
                initial_plan = _run_view(db_session, run)
        except Exception:
            # Saving already succeeded. Return the schedule so a planning error
            # does not invite the caller to create a duplicate on retry.
            db_session.rollback()
            runner.logger.exception("Could not run schedule %s immediately", s.id)
    return CreatedSchedule(**_view(db_session, s).model_dump(), initial_plan=initial_plan)


@router.post("/workflow-schedules/{schedule_id}/run-now")
def run_now(
    schedule_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> RunView:
    s = _own(db_session, schedule_id, user)
    if not _allowed(db_session, user):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Scheduling is not turned on for you.")
    run = runner.fire_one(db_session, s.id, manual_version=body.version)
    if run is None:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Only active schedules can run on demand.")
    return _run_view(db_session, run)


@router.patch("/workflow-schedules/{schedule_id}")
def edit_schedule(
    schedule_id: UUID, body: EditSchedule,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ScheduleView:
    s = _own(db_session, schedule_id, user)
    if s.version != body.version:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This schedule changed since you opened it. Reload and try again.")
    _check_when(body)
    if (s.cadence == "source") != (body.cadence == "source"):
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Create a new schedule to change the trigger type.")
    if s.cadence == "source":
        _check_source(db_session, user, body.source_library_id)
        if s.source_library_id != body.source_library_id:
            s.source_library_id = body.source_library_id
            s.source_since = func.clock_timestamp()
    elif body.source_library_id is not None:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose the Knowledge change trigger to watch a library.")
    s.name = body.name.strip()
    if body.expense_review is not None and body.expense_review != s.expense_review:
        if s.expense_review is None:
            raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Create a new schedule to run Expense Review.")
        validate_inputs(db_session, user, body.expense_review)
        s.expense_review = body.expense_review
    if body.notify_plan_ready is not None and s.expense_review is None:
        s.notify_plan_ready = body.notify_plan_ready
    if body.notify_needs_review is not None:
        s.notify_needs_review = body.notify_needs_review
    if body.notify_run_failed is not None:
        s.notify_run_failed = body.notify_run_failed
    if body.notify_run_complete is not None:
        s.notify_run_complete = body.notify_run_complete
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
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Only an active schedule can be paused. Reload and try again.")
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
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Only a paused schedule can be resumed. Reload and try again.")
    if not _allowed(db_session, user):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Scheduling is not turned on for you. An administrator decides who may schedule workflows.")
    nxt = None
    if s.cadence == "source":
        _check_source(db_session, user, s.source_library_id)
        s.source_since = func.clock_timestamp()
    else:
        nxt = runner.compute_next(s, datetime.datetime.now(datetime.timezone.utc))
        if nxt is None:
            raise NortPoleError(NortPoleErrorCode.CONFLICT, "Its time has passed. Edit the date first.")
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
    include: UUID | None = None,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[RunView]:
    s = _own(db_session, schedule_id, user)
    runs = list(db_session.scalars(select(NortPoleWorkflowRun).where(NortPoleWorkflowRun.schedule_id == s.id)
                                   .order_by(NortPoleWorkflowRun.fired_at.desc()).limit(50)))
    if include is not None and all(run.id != include for run in runs):
        requested = db_session.scalar(select(NortPoleWorkflowRun).where(
            NortPoleWorkflowRun.id == include, NortPoleWorkflowRun.schedule_id == s.id,
        ))
        if requested is not None:
            runs.append(requested)
    return [_run_view(db_session, r) for r in runs]


@router.post("/workflow-schedules/{schedule_id}/runs/{run_id}/retry")
def retry_run(
    schedule_id: UUID,
    run_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> RunView:
    schedule = _own(db_session, schedule_id, user)
    if not _allowed(db_session, user):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Scheduling is not turned on for you.")
    existing = db_session.scalar(select(NortPoleWorkflowRun).where(
        NortPoleWorkflowRun.schedule_id == schedule.id, NortPoleWorkflowRun.retry_of_id == run_id,
    ))
    if existing is not None:
        return _run_view(db_session, existing)
    run = runner.fire_one(db_session, schedule.id, retry_of_id=run_id)
    if run is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Workflow run not found.")
    return _run_view(db_session, run)


class RunOutcomeCheck(BaseModel):
    detail: str


@router.post("/workflow-schedules/{schedule_id}/runs/{run_id}/check-outcome")
def check_run_outcome(
    schedule_id: UUID,
    run_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> RunOutcomeCheck:
    schedule = _own(db_session, schedule_id, user)
    return RunOutcomeCheck(detail=runner.check_outcome(db_session, schedule, run_id))


# ---- sharing: others copy a shared schedule; the copy is theirs and runs as them ----

class ShareBody(BaseModel):
    version: int
    groups: list[str] = Field(default_factory=list, max_length=20)


class SharedView(BaseModel):
    id: UUID
    name: str
    owner_email: str
    when: str
    title: str
    request: str
    desired_output: str
    pack_id: str | None
    already_copied: bool


def _shared_with(db: Session, s: NortPoleWorkflowSchedule, user: User) -> bool:
    return s.expense_review is None and s.owner_id != user.id and s.state != "ended" and bool(set(s.shared_with_groups or []) & group_names_for_user(db, user.id))


@router.put("/workflow-schedules/{schedule_id}/share")
def share_schedule(
    schedule_id: UUID, body: ShareBody,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ScheduleView:
    s = _own(db_session, schedule_id, user)
    if s.version != body.version:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This schedule changed since you opened it. Reload and try again.")
    groups = sorted({g.strip() for g in body.groups if g.strip()})
    if groups and s.expense_review is not None:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Expense Review schedules use a personal CSV and cannot be shared.")
    if groups and s.cadence == "source":
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Knowledge-triggered schedules are personal.")
    mine = group_names_for_user(db_session, user.id)
    if not set(groups) <= mine:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "You can share only with groups you belong to.")
    s.shared_with_groups = groups
    s.version += 1
    db_session.commit()
    _audit(AuditAction.SCHEDULE_CHANGE, user, s, "Shared a schedule" if groups else "Stopped sharing a schedule",
           change="share", groups=groups)
    return _view(db_session, s)


@router.get("/workflow-schedules/shared")
def list_shared(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
    include: UUID | None = None,
) -> list[SharedView]:
    mine = group_names_for_user(db_session, user.id)
    if not mine:
        return []
    copied = {c for c in db_session.scalars(select(NortPoleWorkflowSchedule.copied_from_id)
                                            .where(NortPoleWorkflowSchedule.owner_id == user.id)) if c}
    query = (
        select(NortPoleWorkflowSchedule, User.email)
        .join(User, User.id == NortPoleWorkflowSchedule.owner_id)
        .where(NortPoleWorkflowSchedule.owner_id != user.id, shared_schedule_clause(mine))
    )
    if include is not None:
        query = query.order_by((NortPoleWorkflowSchedule.id == include).desc())
    rows = db_session.execute(query.order_by(NortPoleWorkflowSchedule.created_at.desc()).limit(200)).all()
    return [SharedView(id=s.id, name=s.name, owner_email=email, title=s.title, request=s.request, desired_output=s.desired_output,
                       pack_id=s.pack_id, already_copied=s.id in copied,
                       when=cadence.describe(s.cadence, s.at_time, s.timezone, s.weekday, s.month_day, s.run_on))
            for s, email in rows]


@router.post("/workflow-schedules/{schedule_id}/copy")
def copy_schedule(
    schedule_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ScheduleView:
    src = db_session.get(NortPoleWorkflowSchedule, schedule_id)
    if src is None or not _shared_with(db_session, src, user):
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Schedule not found.")
    if not _allowed(db_session, user):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Scheduling is not turned on for you. An administrator decides who may schedule workflows.")
    _check_limit(db_session, user, writing=True)
    if src.pack_id and _active_template(db_session, src.pack_id, src.pack_template or "") is None:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Its workflow is no longer active, so it cannot be copied.")
    s = NortPoleWorkflowSchedule(owner_id=user.id, name=src.name, pack_id=src.pack_id, pack_template=src.pack_template,
                                 title=src.title, request=src.request, desired_output=src.desired_output,
                                 spread_minutes=random.randint(0, 4), state="active", shared_with_groups=[],  # noqa: S311
                                 copied_from_id=src.id)
    _set_when(s, When(cadence=src.cadence, at_time=src.at_time, timezone=src.timezone, weekday=src.weekday,
                      month_day=src.month_day, run_on=src.run_on), datetime.datetime.now(datetime.timezone.utc))
    db_session.add(s)
    db_session.commit()
    _audit(AuditAction.SCHEDULE_CHANGE, user, s, "Copied a shared schedule", change="copy", source=str(src.id))
    return _view(db_session, s)


# ---- administrators ----

class ControlsUpdate(BaseModel):
    enabled: bool
    source_events_enabled: bool | None = None
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
def get_schedule_controls(_: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> controls.ScheduleControls:
    return controls.load()


@router.put("/admin/workflow-schedules/controls")
def put_schedule_controls(
    body: ControlsUpdate,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> controls.ScheduleControls:
    old = controls.load()
    new = controls.ScheduleControls(version=old.version + 1, enabled=body.enabled,
                                    source_events_enabled=old.source_events_enabled if body.source_events_enabled is None else body.source_events_enabled,
                                    groups=sorted({g.strip() for g in body.groups if g.strip()}), max_per_person=body.max_per_person)
    if (new.source_events_enabled, new.enabled, new.groups) != (old.source_events_enabled, old.enabled, old.groups):
        db_session.execute(update(NortPoleWorkflowSchedule).where(
            NortPoleWorkflowSchedule.cadence == "source",
        ).values(source_since=func.clock_timestamp(), version=NortPoleWorkflowSchedule.version + 1))
        db_session.commit()
    controls.save(new)
    record_audit(AuditAction.SCHEDULE_CONTROLS, AuditOutcome.SUCCESS, actor=user,
                 summary=f"Scheduling {'on' if new.enabled else 'off'}" + (f" for {len(new.groups)} group(s)" if new.enabled and new.groups else ""),
                 details={"enabled": new.enabled, "source_events_enabled": new.source_events_enabled,
                          "groups": new.groups, "max_per_person": new.max_per_person},
                 resource_type="schedule_controls", resource_id="workspace")
    return new


@router.get("/admin/workflow-schedules")
def list_all(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[AdminScheduleView]:
    out = []
    rows = db_session.execute(select(NortPoleWorkflowSchedule, User.email).join(User, User.id == NortPoleWorkflowSchedule.owner_id)
                              .order_by(NortPoleWorkflowSchedule.created_at.desc()).limit(500)).all()
    for s, email in rows:
        last = db_session.scalar(select(NortPoleWorkflowRun.outcome).where(NortPoleWorkflowRun.schedule_id == s.id)
                                 .order_by(NortPoleWorkflowRun.fired_at.desc()).limit(1))
        out.append(AdminScheduleView(id=s.id, owner_email=email, when=cadence.describe(s.cadence, s.at_time, s.timezone, s.weekday, s.month_day, s.run_on),
                                     state=s.state, pause_reason=s.pause_reason, next_run_at=s.next_run_at, last_outcome=last, last_fired_at=s.last_fired_at))
    return out


@router.post("/admin/workflow-schedules/{schedule_id}/pause")
def admin_pause(
    schedule_id: UUID,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> AdminScheduleView:
    s = db_session.get(NortPoleWorkflowSchedule, schedule_id)
    if s is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Schedule not found.")
    if s.state != "active":
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Only an active schedule can be paused.")
    runner.pause(db_session, s, "admin", actor=user)
    return next(v for v in list_all(_=user, db_session=db_session) if v.id == s.id)


@router.post("/admin/workflow-schedules/run-due")
def run_due_now(_: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> dict[str, int]:
    """Fire what is due now, as the background worker does every five minutes; for deployments without the worker."""
    return {"fired": runner.run_due()}
