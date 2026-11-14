"""Firing scheduled workflows. Each run makes a draft and plans it as the owner, then stops: the plan waits in the
owner's Inbox. A newer run replaces a plan that is still waiting; after three plans in a row are not accepted, or
three runs in a row cannot make a plan, the schedule pauses and the owner is told.

Claiming is a short transaction with row locks (two workers never fire the same schedule); the slow planning call
happens afterwards, holding no lock. Missed runs are not caught up: a schedule fires once and moves on."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from nortpole.configs.constants import NotificationType
from nortpole.db.models import User
from nortpole.db.notification import create_notification
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.knowledge.knowledge_access.groups import group_names_for_user
from nortpole.governance.route_policy.audit import record_audit
from nortpole.work.tasks.models import NortPoleTask
from nortpole.work.tasks.states import TaskState
from nortpole.utils.audit import AuditAction, AuditOutcome
from nortpole.utils.logger import setup_logger
from nortpole.work.workflow_schedules import cadence, controls
from nortpole.work.workflow_schedules.models import NortPoleWorkflowRun, NortPoleWorkflowSchedule

logger = setup_logger()

MAX_STREAK = 3
TICK_LIMIT = 20
ACCEPTED = {TaskState.PLAN_ACCEPTED.value, TaskState.RUNNING.value, TaskState.DRAFT_READY.value, TaskState.RUN_FAILED.value, TaskState.APPROVED.value}
NOT_ACCEPTED = {TaskState.PLAN_REVIEW.value, TaskState.CANCELLED.value, TaskState.DRAFT.value, TaskState.SUPERSEDED.value}
PAUSE_TEXT = {
    "unaccepted": "Its last 3 plans were not accepted. Resume it when it is useful again.",
    "skipped": "Its last 3 runs could not make a plan. Check the workflow, then resume it.",
    "scheduling_off": "Scheduling is turned off for you by an administrator.",
    "owner_inactive": "The owner's account is not active.",
    "admin": "An administrator paused it.",
    "owner": "You paused it.",
}


def compute_next(s: NortPoleWorkflowSchedule, after: datetime.datetime) -> datetime.datetime | None:
    return cadence.next_run(s.cadence, s.at_time, s.timezone, s.weekday, s.month_day, s.run_on, after, s.spread_minutes)


def pause(db: Session, s: NortPoleWorkflowSchedule, reason: str, *, actor: User | None, notify: bool = True) -> None:
    s.state, s.pause_reason, s.next_run_at = "paused", reason, None
    s.version += 1
    db.commit()
    record_audit(AuditAction.SCHEDULE_STATE, AuditOutcome.SUCCESS, actor=actor, summary=f"Schedule paused ({reason})",
                 details={"state": "paused", "reason": reason}, resource_type="workflow_schedule", resource_id=str(s.id))
    if notify:
        try:
            create_notification(user_id=s.owner_id, notif_type=NotificationType.SCHEDULE_PAUSED, db_session=db,
                                title=f'Scheduled workflow "{s.name}" was paused', description=PAUSE_TEXT.get(reason, reason),
                                additional_data={"schedule_id": str(s.id), "at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        except Exception:
            logger.exception("Could not notify the owner of a paused schedule %s", s.id)
            db.rollback()


def claim_due(db: Session, now: datetime.datetime, limit: int = TICK_LIMIT) -> list[uuid.UUID]:
    rows = db.scalars(
        select(NortPoleWorkflowSchedule)
        .where(NortPoleWorkflowSchedule.state == "active", NortPoleWorkflowSchedule.next_run_at <= now)
        .order_by(NortPoleWorkflowSchedule.next_run_at).limit(limit).with_for_update(skip_locked=True)
    ).all()
    ids = []
    for s in rows:
        ids.append(s.id)
        s.last_fired_at = now
        s.next_run_at = compute_next(s, now)  # no catch-up: the next time after now
        if s.next_run_at is None:
            s.state = "ended"  # a one-time schedule, firing now for the last time
    db.commit()
    return ids


def _record(db: Session, s: NortPoleWorkflowSchedule, outcome: str, reason: str | None = None, task_id: uuid.UUID | None = None,
            route_kind: str | None = None, tokens: tuple[int, int] = (0, 0), actor: User | None = None) -> NortPoleWorkflowRun:
    run = NortPoleWorkflowRun(schedule_id=s.id, task_id=task_id, outcome=outcome, reason=reason, route_kind=route_kind,
                              input_tokens=tokens[0], output_tokens=tokens[1])
    db.add(run)
    db.commit()
    # No title or request text in the audit record.
    record_audit(AuditAction.SCHEDULE_FIRE, AuditOutcome.SUCCESS if outcome == "plan_ready" else AuditOutcome.FAILURE, actor=actor,
                 summary=f"Scheduled run: {outcome.replace('_', ' ')}", details={"outcome": outcome, "run": str(run.id)},
                 resource_type="workflow_schedule", resource_id=str(s.id))
    return run


def _skip(db: Session, s: NortPoleWorkflowSchedule, reason: str, user: User | None) -> NortPoleWorkflowRun:
    s.skip_streak += 1
    run = _record(db, s, "skipped", reason, actor=user)
    if s.skip_streak >= MAX_STREAK:
        pause(db, s, "skipped", actor=user)
    else:
        db.commit()
    return run


def _new_task(db: Session, s: NortPoleWorkflowSchedule) -> NortPoleTask | str:
    """The draft for this run, from the active pack version, or a reason it cannot be made."""
    if not s.pack_id:
        return NortPoleTask(owner_id=s.owner_id, title=s.title, request=s.request, desired_output=s.desired_output,
                            state=TaskState.DRAFT.value, version=1, schedule_id=s.id)
    from nortpole.work.packs.api import _active_versions

    v = next((x for x in _active_versions(db) if x.pack_id == s.pack_id), None)
    t = next((x for x in v.manifest["templates"] if x["id"] == s.pack_template), None) if v else None
    if v is None or t is None:
        return "Its pack or workflow is no longer active."
    rules = list(v.manifest.get("review_rules", [])) + list(t.get("review_rules", []))
    return NortPoleTask(owner_id=s.owner_id, title=s.title, request=s.request, desired_output=s.desired_output,
                        state=TaskState.DRAFT.value, version=1, pack_id=v.pack_id, pack_version=v.version,
                        pack_template=s.pack_template, review_rules=rules or None, schedule_id=s.id)


def fire_one(db: Session, schedule_id: uuid.UUID) -> NortPoleWorkflowRun | None:
    s = db.get(NortPoleWorkflowSchedule, schedule_id)
    if s is None or s.state == "paused":
        return None
    user = db.get(User, s.owner_id)
    if user is None or not user.is_active:
        pause(db, s, "owner_inactive", actor=None, notify=False)
        return _record(db, s, "paused", PAUSE_TEXT["owner_inactive"])
    if not controls.allowed_for(controls.load(), group_names_for_user(db, user.id)):
        pause(db, s, "scheduling_off", actor=user)
        return _record(db, s, "paused", PAUSE_TEXT["scheduling_off"], actor=user)

    # The previous run's plan: accepted resets the count; still waiting is replaced, unless this is the third in a row.
    prev = db.scalar(select(NortPoleWorkflowRun).where(NortPoleWorkflowRun.schedule_id == s.id, NortPoleWorkflowRun.task_id.isnot(None))
                     .order_by(NortPoleWorkflowRun.fired_at.desc()).limit(1))
    prev_task = db.get(NortPoleTask, prev.task_id) if prev and prev.task_id else None
    if prev_task is not None and prev_task.state in NOT_ACCEPTED:
        if prev_task.state == TaskState.PLAN_REVIEW.value and s.unaccepted_streak + 1 < MAX_STREAK:
            # The same version check people use: if the owner accepted a moment ago, the accept wins.
            db.execute(update(NortPoleTask)
                              .where(NortPoleTask.id == prev_task.id, NortPoleTask.state == TaskState.PLAN_REVIEW.value,
                                     NortPoleTask.version == prev_task.version)
                              .values(state=TaskState.SUPERSEDED.value, version=prev_task.version + 1))
            db.commit()
            db.refresh(prev_task)
        if prev_task.state in ACCEPTED:
            s.unaccepted_streak = 0
        else:
            s.unaccepted_streak += 1
            if s.unaccepted_streak >= MAX_STREAK:
                pause(db, s, "unaccepted", actor=user)
                return _record(db, s, "paused", PAUSE_TEXT["unaccepted"], actor=user)
    elif prev_task is not None and prev_task.state in ACCEPTED:
        s.unaccepted_streak = 0
    db.commit()

    task = _new_task(db, s)
    if isinstance(task, str):
        return _skip(db, s, task, user)
    db.add(task)
    db.commit()
    from nortpole.work.tasks.api import plan_task

    try:
        final, result = plan_task(db, task.id, user, 1, scheduled=True)
    except NortPoleError as e:  # pack requirements refused before planning: the draft never started
        db.rollback()
        db.delete(db.get(NortPoleTask, task.id))
        db.commit()
        return _skip(db, s, e.detail, user)
    if final.state == TaskState.PLAN_REVIEW.value and result is not None:
        s.skip_streak = 0
        db.commit()
        return _record(db, s, "plan_ready", None, final.id, result.route_kind, (result.input_tokens, result.output_tokens), actor=user)
    s.skip_streak += 1
    run = _record(db, s, "plan_failed", final.plan_error, final.id, actor=user)
    if s.skip_streak >= MAX_STREAK:
        pause(db, s, "skipped", actor=user)
    return run


def run_due(now: datetime.datetime | None = None, limit: int = TICK_LIMIT) -> int:
    """Claim and fire what is due. Returns how many were fired. One failure never stops the others."""
    from nortpole.db.engine.sql_engine import get_session_with_current_tenant

    now = now or datetime.datetime.now(datetime.timezone.utc)
    with get_session_with_current_tenant() as db:
        ids = claim_due(db, now, limit)
    for sid in ids:
        try:
            with get_session_with_current_tenant() as db:
                fire_one(db, sid)
        except Exception:
            logger.exception("scheduled run failed schedule_id=%s", sid)
    return len(ids)
