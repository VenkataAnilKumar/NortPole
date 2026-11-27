"""Read durable evidence for interrupted schedule runs and eligible retries."""

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from nortpole.agents.models import RunStatus
from nortpole.db.models import ChatMessage, ChatSession
from nortpole.work.actions.models import NortPoleAction
from nortpole.work.tasks.models import NortPoleTask
from nortpole.work.tasks.states import TaskState
from nortpole.work.workflow_schedules.models import NortPoleWorkflowRun, NortPoleWorkflowSchedule


def _action_states(db: Session, task: NortPoleTask) -> set[str]:
    return set(db.scalars(select(NortPoleAction.state).where(
        NortPoleAction.task_id == task.id, NortPoleAction.owner_id == task.owner_id,
    )))


def is_failed_plan(task: NortPoleTask) -> bool:
    return task.state == TaskState.PLAN_FAILED.value and not any((
        task.plan, task.draft_text, task.draft_hash, task.draft_versions,
        task.drafted_at, task.approved_hash, task.approved_at, task.exported_at,
    ))


def can_retry(
    db: Session, schedule: NortPoleWorkflowSchedule, run: NortPoleWorkflowRun, task: NortPoleTask | None,
) -> bool:
    if (
        run.outcome != "plan_failed"
        or run.completed_at is None
        or run.schedule_version != schedule.version
        or schedule.state not in {"active", "ended"}
        or schedule.expense_review is not None
        or run.chat_session_id is not None
        or run.source_event_id is not None
        or run.drive_source is not None
        or task is None
        or task.owner_id != schedule.owner_id
        or task.schedule_id != schedule.id
        or task.id != run.task_id
        or not is_failed_plan(task)
    ):
        return False
    later = db.scalar(select(NortPoleWorkflowRun.id).where(
        NortPoleWorkflowRun.schedule_id == schedule.id,
        tuple_(NortPoleWorkflowRun.fired_at, NortPoleWorkflowRun.id) > tuple_(run.fired_at, run.id),
    ).limit(1))
    return later is None and not _action_states(db, task)


def saved_outcome(
    db: Session, schedule: NortPoleWorkflowSchedule, run: NortPoleWorkflowRun,
) -> tuple[str | None, str]:
    """Return an outcome only from an artifact explicitly linked to this attempt."""
    if run.chat_session_id is not None and run.chat_result_id is not None:
        review_state = db.execute(
            select(ChatMessage.receipt_review_needs_review)
            .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
            .where(
                ChatSession.id == run.chat_session_id,
                ChatSession.user_id == schedule.owner_id,
                ChatSession.deleted.is_(False),
                ChatSession.incognito_record_mode.is_(None),
                ChatMessage.id == run.chat_result_id,
                ChatMessage.response_status == RunStatus.COMPLETE,
                ChatMessage.receipt_review_needs_review.is_not(None),
            )
        ).one_or_none()
        if review_state is not None:
            return ("needs_review" if review_state[0] else "review_complete"), "The saved review was recovered."
    task = db.get(NortPoleTask, run.task_id) if run.task_id else None
    if task and task.owner_id == schedule.owner_id and task.schedule_id == schedule.id:
        actions = _action_states(db, task)
        if actions - {"succeeded", "cancelled"}:
            return None, "An external action still needs review. Open the draft to check its status."
        draft_saved = bool(task.draft_text or task.draft_hash or task.approved_at)
        if task.plan or draft_saved:
            detail = "The saved draft was recovered." if draft_saved else "The saved plan was recovered."
            if actions:
                detail = "The linked task has an external action. Open the draft to review its status."
            return "plan_ready", detail
        if actions:
            return None, "An external action exists. Open the draft to review its status."
        if is_failed_plan(task):
            return "plan_failed", task.plan_error or "The planner recorded a failure before producing a plan."
    return None, "NortPole could not verify the outcome. This run still needs review."
