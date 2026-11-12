"""Task states and the moves between them. Pure; no database."""

from enum import Enum


class TaskState(str, Enum):
    DRAFT = "draft"  # editable; nothing runs
    PLANNING = "planning"  # started; a plan is being drafted
    PLAN_REVIEW = "plan_review"  # the owner reviews the proposed plan
    PLAN_ACCEPTED = "plan_accepted"  # the owner accepted; the run comes next
    PLAN_FAILED = "plan_failed"  # no plan could be made; can be edited and restarted
    RUNNING = "running"  # gathering evidence and drafting
    DRAFT_READY = "draft_ready"  # a cited draft waits for the owner
    RUN_FAILED = "run_failed"  # the run stopped; can be retried
    CANCELLED = "cancelled"


class TaskAction(str, Enum):
    START = "start"
    PLAN_READY = "plan_ready"
    PLAN_FAILED = "plan_failed"
    ACCEPT = "accept"
    REVISE = "revise"
    CANCEL = "cancel"
    RUN = "run"
    DRAFT_DONE = "draft_done"
    RUN_FAILED = "run_failed"


ALLOWED: dict[tuple[TaskState, TaskAction], TaskState] = {
    (TaskState.DRAFT, TaskAction.START): TaskState.PLANNING,
    (TaskState.DRAFT, TaskAction.CANCEL): TaskState.CANCELLED,
    (TaskState.PLANNING, TaskAction.PLAN_READY): TaskState.PLAN_REVIEW,
    (TaskState.PLANNING, TaskAction.PLAN_FAILED): TaskState.PLAN_FAILED,
    (TaskState.PLAN_REVIEW, TaskAction.ACCEPT): TaskState.PLAN_ACCEPTED,
    (TaskState.PLAN_REVIEW, TaskAction.REVISE): TaskState.DRAFT,
    (TaskState.PLAN_REVIEW, TaskAction.CANCEL): TaskState.CANCELLED,
    (TaskState.PLAN_FAILED, TaskAction.REVISE): TaskState.DRAFT,
    (TaskState.PLAN_FAILED, TaskAction.CANCEL): TaskState.CANCELLED,
    (TaskState.PLAN_ACCEPTED, TaskAction.RUN): TaskState.RUNNING,
    (TaskState.PLAN_ACCEPTED, TaskAction.CANCEL): TaskState.CANCELLED,
    (TaskState.RUNNING, TaskAction.DRAFT_DONE): TaskState.DRAFT_READY,
    (TaskState.RUNNING, TaskAction.RUN_FAILED): TaskState.RUN_FAILED,
    (TaskState.RUN_FAILED, TaskAction.RUN): TaskState.RUNNING,
    (TaskState.RUN_FAILED, TaskAction.CANCEL): TaskState.CANCELLED,
    (TaskState.DRAFT_READY, TaskAction.CANCEL): TaskState.CANCELLED,
}

EDITABLE = frozenset({TaskState.DRAFT})


class InvalidTransition(Exception):
    def __init__(self, state: TaskState, action: TaskAction) -> None:
        super().__init__(f"A task that is {state.value.replace('_', ' ')} cannot {action.value.replace('_', ' ')}.")
        self.state = state
        self.action = action


def next_state(state: TaskState, action: TaskAction) -> TaskState:
    try:
        return ALLOWED[(state, action)]
    except KeyError:
        raise InvalidTransition(state, action) from None
