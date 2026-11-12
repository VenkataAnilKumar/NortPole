"""Reviewed-task endpoints. Each person sees and changes only their own tasks.

Every write names the task version it was based on; a stale version is refused
with a conflict, so a second click or an old tab cannot start a task twice or
overwrite newer edits.
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.route_policy.audit import record_audit
from evolvxsi.tasks.models import EvolvXSITask
from evolvxsi.tasks.drafter import draft_answer
from evolvxsi.tasks.evidence import gather_evidence
from evolvxsi.tasks.planner import PlanError, draft_plan
from evolvxsi.tasks.states import EDITABLE, InvalidTransition, TaskAction, TaskState, next_state
from evolvxsi.utils.audit import AuditAction, AuditOutcome
from evolvxsi.utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(prefix="/tasks")

MAX_TITLE = 200
MAX_TEXT = 8000


class TaskView(BaseModel):
    id: UUID
    title: str
    request: str
    desired_output: str
    state: TaskState
    version: int
    plan: list[str] | None
    plan_route: str | None
    plan_error: str | None
    revision_note: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    started_at: datetime.datetime | None
    draft_text: str | None = None
    draft_sources: list[dict] | None = None
    draft_route: str | None = None
    run_error: str | None = None
    drafted_at: datetime.datetime | None = None


class TaskDraft(BaseModel):
    title: str
    request: str
    desired_output: str = ""

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("A task needs a title.")
        if len(v) > MAX_TITLE:
            raise ValueError(f"A title can be at most {MAX_TITLE} characters.")
        return v

    @field_validator("request")
    @classmethod
    def _request(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Describe what the task should do.")
        if len(v) > MAX_TEXT:
            raise ValueError(f"A request can be at most {MAX_TEXT} characters.")
        return v

    @field_validator("desired_output")
    @classmethod
    def _out(cls, v: str) -> str:
        if len(v) > MAX_TEXT:
            raise ValueError(f"The desired output can be at most {MAX_TEXT} characters.")
        return v.strip()


class TaskEdit(TaskDraft):
    version: int


class VersionOnly(BaseModel):
    version: int


class Revise(BaseModel):
    version: int
    note: str = ""


def _view(t: EvolvXSITask) -> TaskView:
    return TaskView.model_validate(t.as_dict())


def _own(db: Session, task_id: UUID, user: User) -> EvolvXSITask:
    task = db.scalar(select(EvolvXSITask).where(EvolvXSITask.id == task_id, EvolvXSITask.owner_id == user.id))
    if task is None:
        # Same answer for "missing" and "someone else's", so existence is not revealed.
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Task not found.")
    return task


def _move(db: Session, task_id: UUID, user: User, version: int, action: TaskAction, **values: object) -> EvolvXSITask:
    """Apply one state move as a single conditional update on (owner, state,
    version). Exactly one of two racing requests can win."""
    task = _own(db, task_id, user)
    try:
        new_state = next_state(TaskState(task.state), action)
    except InvalidTransition as e:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, str(e)) from e
    if task.version != version:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This task changed since you opened it. Reload and try again.")
    result = db.execute(
        update(EvolvXSITask)
        .where(
            EvolvXSITask.id == task_id,
            EvolvXSITask.owner_id == user.id,
            EvolvXSITask.state == task.state,
            EvolvXSITask.version == version,
        )
        .values(state=new_state.value, version=EvolvXSITask.version + 1, updated_at=func.now(), **values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This task changed since you opened it. Reload and try again.")
    db.commit()
    db.expire_all()
    return _own(db, task_id, user)


def _audit(user: User, action: AuditAction, task: EvolvXSITask, summary: str, outcome: AuditOutcome = AuditOutcome.SUCCESS) -> None:
    # Title and request text stay out of the audit record.
    record_audit(action, outcome, actor=user, summary=summary, resource_type="task", resource_id=str(task.id))


@router.get("")
def list_tasks(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[TaskView]:
    rows = db_session.scalars(
        select(EvolvXSITask).where(EvolvXSITask.owner_id == user.id).order_by(EvolvXSITask.updated_at.desc()).limit(200)
    )
    return [_view(t) for t in rows]


@router.get("/{task_id}")
def get_task(
    task_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    return _view(_own(db_session, task_id, user))


@router.post("")
def create_draft(
    body: TaskDraft,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """Saving a draft creates no work."""
    task = EvolvXSITask(
        owner_id=user.id, title=body.title, request=body.request, desired_output=body.desired_output,
        state=TaskState.DRAFT.value, version=1,
    )
    db_session.add(task)
    db_session.commit()
    return _view(task)


@router.patch("/{task_id}")
def edit_draft(
    task_id: UUID,
    body: TaskEdit,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    task = _own(db_session, task_id, user)
    if TaskState(task.state) not in EDITABLE:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Only a draft can be edited.")
    result = db_session.execute(
        update(EvolvXSITask)
        .where(EvolvXSITask.id == task_id, EvolvXSITask.owner_id == user.id,
               EvolvXSITask.state == TaskState.DRAFT.value, EvolvXSITask.version == body.version)
        .values(title=body.title, request=body.request, desired_output=body.desired_output,
                version=EvolvXSITask.version + 1, updated_at=func.now())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db_session.rollback()
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This task changed since you opened it. Reload and try again.")
    db_session.commit()
    db_session.expire_all()
    return _view(_own(db_session, task_id, user))


@router.post("/{task_id}/start")
def start_task(
    task_id: UUID,
    body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """The explicit start. Moves the draft to planning atomically (a duplicate
    start is refused), then drafts a plan through the route policy."""
    task = _move(db_session, task_id, user, body.version, TaskAction.START,
                 started_at=func.now(), plan=None, plan_error=None, plan_route=None)
    _audit(user, AuditAction.TASK_START, task, "Started a task")
    try:
        result = draft_plan(db_session, user, task.title, task.request, task.desired_output)
    except PlanError as e:
        return _view(_move(db_session, task_id, user, task.version, TaskAction.PLAN_FAILED, plan_error=str(e)))
    except EvolvXSIError as e:
        # A policy block keeps its own audit record; tell the owner plainly.
        return _view(_move(db_session, task_id, user, task.version, TaskAction.PLAN_FAILED, plan_error=e.detail))
    except Exception:
        logger.exception("task planning failed task_id=%s", task_id)
        return _view(_move(db_session, task_id, user, task.version, TaskAction.PLAN_FAILED,
                           plan_error="The plan could not be drafted. Try again in a moment."))
    return _view(_move(db_session, task_id, user, task.version, TaskAction.PLAN_READY,
                       plan=result.steps, plan_route=result.route_kind))


@router.post("/{task_id}/plan/accept")
def accept_plan(
    task_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    task = _move(db_session, task_id, user, body.version, TaskAction.ACCEPT)
    _audit(user, AuditAction.TASK_PLAN_ACCEPT, task, f"Accepted a plan of {len(task.plan or [])} step(s)")
    return _view(task)


@router.post("/{task_id}/plan/revise")
def revise_plan(
    task_id: UUID, body: Revise,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """Back to an editable draft; the owner edits and starts again."""
    return _view(_move(db_session, task_id, user, body.version, TaskAction.REVISE,
                       revision_note=body.note.strip()[:MAX_TEXT] or None))


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    task = _move(db_session, task_id, user, body.version, TaskAction.CANCEL)
    _audit(user, AuditAction.TASK_CANCEL, task, "Cancelled a task")
    return _view(task)


@router.post("/{task_id}/run")
def run_task(
    task_id: UUID,
    body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """Run an accepted plan (or retry a failed run): gather evidence as the
    owner, then draft a cited answer through the route policy. The move to
    running is atomic, so the same run cannot start twice."""
    task = _move(db_session, task_id, user, body.version, TaskAction.RUN, run_error=None)
    _audit(user, AuditAction.TASK_RUN, task, "Started a task run")
    try:
        evidence = gather_evidence(db_session, user, f"{task.title}\n{task.request}")
        result = draft_answer(db_session, user, task.title, task.request, task.plan or [], evidence)
    except EvolvXSIError as e:
        return _view(_move(db_session, task_id, user, task.version, TaskAction.RUN_FAILED, run_error=e.detail))
    except Exception:
        logger.exception("task run failed task_id=%s", task_id)
        return _view(_move(db_session, task_id, user, task.version, TaskAction.RUN_FAILED,
                           run_error="The run stopped before a draft was ready. Try again in a moment."))
    by_n = {e.n: e for e in evidence}
    sources = [
        {"n": e.n, "doc_id": e.doc_id, "title": e.title, "link": e.link, "cited": e.n in result.cited}
        for e in by_n.values()
    ]
    if result.removed_citations:
        logger.info("task run removed %s citation(s) to sources not provided task_id=%s", result.removed_citations, task_id)
    return _view(_move(db_session, task_id, user, task.version, TaskAction.DRAFT_DONE,
                       draft_text=result.text, draft_sources=sources, draft_route=result.route_kind,
                       drafted_at=func.now()))
