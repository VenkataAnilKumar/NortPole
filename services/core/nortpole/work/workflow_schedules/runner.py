"""Run scheduled workflows as the owner.

Plans wait in the owner's Inbox, and a newer run can replace a plan that is still
waiting. Expense Reviews save their result in Chat. Repeated failures pause a schedule.

The scheduler claims due occurrences under row locks and executes them after
releasing those locks. A late tick fires once and advances to the next occurrence.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from nortpole.configs.constants import NotificationType
from nortpole.db.models import User
from nortpole.db.notification import create_notification
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.knowledge.knowledge_access.groups import group_names_for_user
from nortpole.governance.route_policy.audit import record_audit
from nortpole.redis.lock_context import RedisSharedLockAcquisitionError, redis_shared_lock
from nortpole.work.tasks.models import NortPoleTask
from nortpole.work.tasks.states import TaskState
from nortpole.utils.audit import AuditAction, AuditOutcome
from nortpole.utils.logger import setup_logger
from nortpole.work.workflow_schedules import cadence, controls, recovery, source_events
from nortpole.work.workflow_schedules.drive_csv import NoNewDriveCsv
from nortpole.work.workflow_schedules.expense_review import run_drive_expense_review, run_expense_review
from nortpole.work.workflow_schedules.models import DriveRunSource, KnowledgeTriggerInput, NortPoleWorkflowRun, NortPoleWorkflowSchedule
from nortpole.work.workflow_schedules.notifications import notify_scheduled_run
from shared_configs.contextvars import get_current_tenant_id

logger = setup_logger()

MAX_STREAK = 3
TICK_LIMIT = 20
RunTrigger = Literal["timer", "manual", "chat", "retry", "source"]
INTERRUPTED_AFTER = datetime.timedelta(minutes=30)
CHAT_QUEUE_TIMEOUT = datetime.timedelta(hours=1)
ACCEPTED = {TaskState.PLAN_ACCEPTED.value, TaskState.RUNNING.value, TaskState.DRAFT_READY.value, TaskState.RUN_FAILED.value, TaskState.APPROVED.value}
NOT_ACCEPTED = {TaskState.PLAN_REVIEW.value, TaskState.CANCELLED.value, TaskState.DRAFT.value, TaskState.SUPERSEDED.value}
PAUSE_TEXT = {
    "unaccepted": "Its last 3 plans were not accepted. Resume it when it is useful again.",
    "skipped": "Its last 3 runs could not finish. Check the workflow, then resume it.",
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


def queue_run(db: Session, schedule: NortPoleWorkflowSchedule, trigger: RunTrigger,
              *, retry_of_id: uuid.UUID | None = None) -> NortPoleWorkflowRun:
    run = NortPoleWorkflowRun(
        schedule_id=schedule.id, schedule_version=schedule.version, trigger=trigger, outcome="queued",
        retry_of_id=retry_of_id,
    )
    db.add(run)
    return run


def claim_due(db: Session, now: datetime.datetime, limit: int = TICK_LIMIT) -> list[uuid.UUID]:
    rows = db.scalars(
        select(NortPoleWorkflowSchedule)
        .where(NortPoleWorkflowSchedule.state == "active", NortPoleWorkflowSchedule.next_run_at <= now)
        .order_by(NortPoleWorkflowSchedule.next_run_at).limit(limit).with_for_update(skip_locked=True)
    ).all()
    runs = []
    for schedule in rows:
        runs.append(queue_run(db, schedule, "timer"))
        schedule.last_fired_at = now
        schedule.next_run_at = compute_next(schedule, now)  # no catch-up
        if schedule.next_run_at is None:
            schedule.state = "ended"  # the final occurrence is already queued
    db.flush()
    ids = [run.id for run in runs]
    db.commit()
    return ids


def effective_outcome(run: NortPoleWorkflowRun, now: datetime.datetime) -> str:
    if run.outcome == "queued" and run.trigger == "chat" and run.fired_at + CHAT_QUEUE_TIMEOUT <= now:
        return "expired"
    if run.outcome == "running" and run.started_at and run.started_at + INTERRUPTED_AFTER <= now:
        return "interrupted"
    return run.outcome


def _record(db: Session, s: NortPoleWorkflowSchedule, run: NortPoleWorkflowRun, outcome: str,
            reason: str | None = None, task_id: uuid.UUID | None = None,
            route_kind: str | None = None, tokens: tuple[int, int] = (0, 0), actor: User | None = None,
            chat_session_id: uuid.UUID | None = None, drive_source: DriveRunSource | None = None) -> NortPoleWorkflowRun:
    run.outcome = outcome
    run.completed_at = datetime.datetime.now(datetime.timezone.utc)
    run.reason = reason
    if task_id is not None:
        run.task_id = task_id
    run.route_kind = route_kind
    run.input_tokens, run.output_tokens = tokens
    if chat_session_id is not None:
        run.chat_session_id = chat_session_id
    if drive_source is not None:
        run.drive_source = drive_source
    db.commit()
    # No title or request text in the audit record.
    record_audit(AuditAction.SCHEDULE_FIRE, AuditOutcome.SUCCESS if outcome in {"plan_ready", "review_complete", "needs_review", "no_new_csv"} else AuditOutcome.FAILURE, actor=actor,
                 summary=f"Scheduled run: {outcome.replace('_', ' ')}",
                 details={"outcome": outcome, "run": str(run.id), "retry_of": str(run.retry_of_id) if run.retry_of_id else None},
                 resource_type="workflow_schedule", resource_id=str(s.id))
    notify_scheduled_run(db, s, run)
    return run


def _skip(db: Session, s: NortPoleWorkflowSchedule, run: NortPoleWorkflowRun, reason: str, user: User | None) -> NortPoleWorkflowRun:
    s.skip_streak += 1
    is_drive = s.expense_review is not None and s.expense_review.drive_source is not None
    outcome = "interrupted" if run.chat_session_id else "drive_skipped" if is_drive else "skipped"
    run = _record(db, s, run, outcome, reason, actor=user)
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


def _schedule_lock(schedule_id: uuid.UUID):
    return redis_shared_lock(
        f"workflow_schedule:{get_current_tenant_id()}:{schedule_id}",
        max_time_lock_held_s=900, wait_for_lock_s=1, logger=logger,
    )


def _retry_task(db: Session, schedule: NortPoleWorkflowSchedule, source_id: uuid.UUID) -> NortPoleTask:
    source = db.get(NortPoleWorkflowRun, source_id, populate_existing=True)
    original = db.get(NortPoleTask, source.task_id, with_for_update=True, populate_existing=True) if source and source.task_id else None
    if source is None or original is None or source.schedule_id != schedule.id or not recovery.can_retry(db, schedule, source, original):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This run is no longer eligible for a retry.")
    task = _new_task(db, schedule)
    fields = ("title", "request", "desired_output", "pack_id", "pack_version", "pack_template", "review_rules")
    if isinstance(task, str) or any(getattr(task, field) != getattr(original, field) for field in fields):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The workflow has changed. Use Run now with the current settings.")
    return task


def check_outcome(db: Session, schedule: NortPoleWorkflowSchedule, run_id: uuid.UUID) -> str:
    try:
        with _schedule_lock(schedule.id):
            run = db.get(NortPoleWorkflowRun, run_id, populate_existing=True)
            if run is None or run.schedule_id != schedule.id:
                raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Workflow run not found.")
            now = datetime.datetime.now(datetime.timezone.utc)
            if effective_outcome(run, now) != "interrupted":
                return "The latest outcome is already recorded."
            outcome, detail = recovery.saved_outcome(db, schedule, run)
            changes: dict[str, object] = {}
            if outcome is not None:
                changes.update(outcome=outcome, completed_at=run.completed_at or now, reason=detail)
            elif detail not in (run.reason or ""):
                changes["reason"] = f"{run.reason}\n{detail}" if run.reason else detail
            if changes:
                changed = db.execute(update(NortPoleWorkflowRun).where(
                    NortPoleWorkflowRun.id == run.id, NortPoleWorkflowRun.outcome == run.outcome,
                ).values(**changes)).rowcount
                db.commit()
                if not changed:
                    return "The latest outcome is already recorded."
            return detail
    except RedisSharedLockAcquisitionError:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This workflow is still running. Check again shortly.") from None


def fire_one(
    db: Session, schedule_id: uuid.UUID, *, manual_version: int | None = None,
    trigger: RunTrigger = "manual", run_id: uuid.UUID | None = None, retry_of_id: uuid.UUID | None = None,
) -> NortPoleWorkflowRun | None:
    """Serialize executions and transition one durable run from queued to running."""
    run = None
    try:
        with _schedule_lock(schedule_id):
            s = db.get(NortPoleWorkflowSchedule, schedule_id, populate_existing=True)
            if manual_version is not None and (
                s is None or s.state != "active" or s.version != manual_version
            ):
                raise NortPoleError(
                    NortPoleErrorCode.CONFLICT,
                    "This schedule is no longer active or has changed. Reload and try again.",
                )
            if s is None:
                return None
            if s.cadence == "source" and run_id is None:
                raise NortPoleError(NortPoleErrorCode.CONFLICT, "This workflow starts when a document changes in Knowledge.")
            prepared_task = None
            if retry_of_id is not None:
                db.refresh(s, with_for_update=True)
                existing = db.scalar(select(NortPoleWorkflowRun).where(
                    NortPoleWorkflowRun.retry_of_id == retry_of_id, NortPoleWorkflowRun.schedule_id == s.id,
                ))
                if existing is not None:
                    return existing
                prepared_task = _retry_task(db, s, retry_of_id)
                trigger = "retry"
            run = db.get(NortPoleWorkflowRun, run_id, populate_existing=True) if run_id else None
            if run_id and (run is None or run.schedule_id != s.id or run.outcome != "queued"):
                return None
            if run is None:
                if s.state == "paused":
                    return None
                run = queue_run(db, s, trigger, retry_of_id=retry_of_id)
            if s.state == "paused" or run.schedule_version != s.version:
                return _record(db, s, run, "skipped", "The schedule changed or was paused before the run started.")
            run.outcome = "running"
            run.started_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
            # The approved settings must still match after the commit refreshed the row.
            db.refresh(s)
            if s.state == "paused" or run.schedule_version != s.version:
                return _record(db, s, run, "skipped", "The schedule changed or was paused before the run started.")
            return _fire_locked(db, s, run, prepared_task=prepared_task)
    except RedisSharedLockAcquisitionError:
        if manual_version is not None or retry_of_id is not None:
            raise NortPoleError(
                NortPoleErrorCode.CONFLICT, "This workflow is already running. Check its history shortly.",
            ) from None
        # A timer occurrence remains queued for the next worker tick.
        return None
    except Exception:
        db.rollback()
        if run is not None and run.outcome == "running":
            run.outcome = "interrupted"
            run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            run.reason = "The worker did not finish recording the result."
            db.commit()
        raise


def _fire_locked(db: Session, s: NortPoleWorkflowSchedule, run: NortPoleWorkflowRun,
                 *, prepared_task: NortPoleTask | None = None) -> NortPoleWorkflowRun:
    user = db.get(User, s.owner_id)
    if user is None or not user.is_active:
        pause(db, s, "owner_inactive", actor=None, notify=False)
        return _record(db, s, run, "paused", PAUSE_TEXT["owner_inactive"])
    config = controls.load()
    groups = group_names_for_user(db, user.id)
    if not controls.allowed_for(config, groups):
        pause(db, s, "scheduling_off", actor=user)
        return _record(db, s, run, "paused", PAUSE_TEXT["scheduling_off"], actor=user)

    trigger_input = None
    if run.trigger == "source":
        if not source_events.allowed(config, groups):
            return _record(db, s, run, "skipped", "Knowledge triggers are turned off for this account.", actor=user)
        trigger_input = KnowledgeTriggerInput(
            library_id=run.source_library_id, document_id=run.source_document_id, content_hash=run.source_content_hash,
        )
        try:
            source_events.require_current_source(db, user, trigger_input)
        except NortPoleError as exc:
            return _record(db, s, run, "skipped", exc.detail, actor=user)

    expense_review = s.expense_review
    if expense_review is not None:
        try:
            if expense_review.drive_source is not None:
                outcome, chat_session_id, revision = run_drive_expense_review(db, user, expense_review, s.id, run=run)
                s.skip_streak = 0
                return _record(db, s, run, outcome, actor=user, chat_session_id=chat_session_id, drive_source=revision)
            outcome, chat_session_id = run_expense_review(db, user, expense_review, run=run)
        except NoNewDriveCsv as e:
            db.rollback()
            s.skip_streak = 0
            return _record(db, s, run, "no_new_csv", str(e), actor=user)
        except NortPoleError as e:
            db.rollback()
            return _skip(db, s, run, e.detail, user)
        except Exception:
            db.rollback()
            logger.exception("Scheduled Expense Review failed schedule_id=%s", s.id)
            return _skip(db, s, run, "The expense review could not finish. Check its inputs and try again.", user)
        s.skip_streak = 0
        return _record(db, s, run, outcome, actor=user, chat_session_id=chat_session_id)

    # Capture the validated schedule inputs before a commit can refresh the row.
    task = prepared_task if prepared_task is not None else _new_task(db, s)
    # The previous run's plan: accepted resets the count; still waiting is replaced, unless this is the third in a row.
    prev = db.scalar(select(NortPoleWorkflowRun).where(NortPoleWorkflowRun.schedule_id == s.id, NortPoleWorkflowRun.task_id.isnot(None))
                     .order_by(NortPoleWorkflowRun.fired_at.desc()).limit(1)) if run.retry_of_id is None and trigger_input is None else None
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
                return _record(db, s, run, "paused", PAUSE_TEXT["unaccepted"], actor=user)
    elif prev_task is not None and prev_task.state in ACCEPTED:
        s.unaccepted_streak = 0
    db.commit()

    if isinstance(task, str):
        return _skip(db, s, run, task, user)
    task.knowledge_trigger = trigger_input
    db.add(task)
    db.flush()
    run.task_id = task.id
    db.commit()
    from nortpole.work.tasks.api import plan_task

    try:
        final, result = plan_task(db, task.id, user, 1, scheduled=True)
    except NortPoleError as e:  # pack requirements refused before planning: the draft never started
        db.rollback()
        run.task_id = None
        db.delete(db.get(NortPoleTask, task.id))
        db.commit()
        return _skip(db, s, run, e.detail, user)
    if final.state == TaskState.PLAN_REVIEW.value and result is not None:
        s.skip_streak = 0
        db.commit()
        return _record(db, s, run, "plan_ready", None, final.id, result.route_kind, (result.input_tokens, result.output_tokens), actor=user)
    s.skip_streak += 1
    run = _record(db, s, run, "plan_failed", final.plan_error, final.id, actor=user)
    if s.skip_streak >= MAX_STREAK:
        pause(db, s, "skipped", actor=user)
    return run


def run_due(now: datetime.datetime | None = None, limit: int = TICK_LIMIT) -> int:
    """Claim and fire what is due. Returns how many were fired. One failure never stops the others."""
    from nortpole.db.engine.sql_engine import get_session_with_current_tenant

    now = now or datetime.datetime.now(datetime.timezone.utc)
    with get_session_with_current_tenant() as db:
        claim_due(db, now, limit)
        try:
            source_events.claim_changes(db, now, limit)
        except Exception:
            db.rollback()
            logger.exception("Could not collect Knowledge workflow events")
        queued = db.execute(
            select(NortPoleWorkflowRun.schedule_id, NortPoleWorkflowRun.id)
            .where(NortPoleWorkflowRun.trigger.in_(("timer", "source")), NortPoleWorkflowRun.outcome == "queued")
            .order_by(NortPoleWorkflowRun.fired_at, NortPoleWorkflowRun.id).limit(limit)
        ).all()
    fired = 0
    for schedule_id, run_id in queued:
        try:
            with get_session_with_current_tenant() as db:
                if fire_one(db, schedule_id, run_id=run_id) is not None:
                    fired += 1
        except Exception:
            logger.exception("scheduled run failed schedule_id=%s run_id=%s", schedule_id, run_id)
    return fired
