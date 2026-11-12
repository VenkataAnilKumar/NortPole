import pytest

from evolvxsi.tasks.planner import parse_plan
from evolvxsi.tasks.states import ALLOWED, InvalidTransition, TaskAction, TaskState, next_state


def test_happy_path() -> None:
    s = TaskState.DRAFT
    for action, expected in [
        (TaskAction.START, TaskState.PLANNING),
        (TaskAction.PLAN_READY, TaskState.PLAN_REVIEW),
        (TaskAction.ACCEPT, TaskState.PLAN_ACCEPTED),
    ]:
        s = next_state(s, action)
        assert s is expected


def test_revise_returns_to_an_editable_draft() -> None:
    assert next_state(TaskState.PLAN_REVIEW, TaskAction.REVISE) is TaskState.DRAFT
    assert next_state(TaskState.PLAN_FAILED, TaskAction.REVISE) is TaskState.DRAFT


@pytest.mark.parametrize("state", [s for s in TaskState if s is not TaskState.DRAFT])
def test_only_a_draft_can_start(state: TaskState) -> None:
    with pytest.raises(InvalidTransition):
        next_state(state, TaskAction.START)


def test_accepted_and_cancelled_are_final_for_this_slice() -> None:
    for s in (TaskState.PLAN_ACCEPTED, TaskState.CANCELLED):
        assert not [a for (st, a) in ALLOWED if st is s]


def test_plan_cannot_be_accepted_before_it_exists() -> None:
    with pytest.raises(InvalidTransition):
        next_state(TaskState.PLANNING, TaskAction.ACCEPT)


def test_parse_plan_keeps_numbered_steps_only() -> None:
    text = "Sure, here is the plan:\n1. Find sources\n2) Compare them\n\n3. Draft with citations\nThanks!"
    assert parse_plan(text) == ["Find sources", "Compare them", "Draft with citations"]


def test_parse_plan_caps_the_number_of_steps() -> None:
    assert len(parse_plan("\n".join(f"{i}. step {i}" for i in range(1, 20)))) == 8


def test_parse_plan_empty_when_no_steps() -> None:
    assert parse_plan("no plan here") == []
