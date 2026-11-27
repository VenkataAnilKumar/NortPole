"""Exercise workflow retries and recovery against persisted, owned results."""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import ChatMessage, User
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.query_and_chat.chat_backend import workflow_run_feed
from nortpole.work.actions.models import NortPoleAction
from nortpole.work.tasks import api as tasks_api
from nortpole.work.tasks.models import NortPoleTask
from nortpole.work.tasks.planner import PlanError
from nortpole.work.workflow_schedules import api, recovery, runner
from nortpole.work.workflow_schedules.models import NortPoleWorkflowRun, NortPoleWorkflowSchedule
from tests.nortpole_integration.test_expense_review_runs import _add_run
from tests.nortpole_integration.test_tasks_flow import _up
from tests.nortpole_integration.test_workflow_schedules import PLAN, _new, world  # noqa: F401

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")


def test_retry_reuses_one_linked_attempt_and_preserves_the_next_run(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as db:
        owner = db.get(User, world["ann"])
        other = db.get(User, world["bob"])
        schedule = _new(db, owner)
        version = api.VersionOnly(version=schedule.version)
        with patch.object(tasks_api, "draft_plan", side_effect=PlanError("Model unavailable")):
            failed = api.run_now(schedule.id, version, user=owner, db_session=db)
        assert failed.outcome == "plan_failed"
        assert workflow_run_feed(user=owner, db_session=db).runs[0].can_retry
        with pytest.raises(NortPoleError, match="Schedule not found"):
            api.retry_run(schedule.id, failed.id, user=other, db_session=db)

        running_attempt_ids = []

        def check_during_retry(*_args, **_kwargs):
            with get_session_with_current_tenant() as observer:
                duplicate = api.retry_run(
                    schedule.id, failed.id, user=observer.get(User, owner.id), db_session=observer,
                )
                assert duplicate.outcome == "running"
                running_attempt_ids.append(duplicate.id)
            return PLAN

        with patch.object(tasks_api, "draft_plan", side_effect=check_during_retry) as planner:
            attempt = api.retry_run(schedule.id, failed.id, user=owner, db_session=db)
            duplicate = api.retry_run(schedule.id, failed.id, user=owner, db_session=db)
        planner.assert_called_once()
        assert attempt.id == duplicate.id
        assert running_attempt_ids == [attempt.id]
        assert attempt.outcome == "plan_ready" and attempt.task_state == "plan_review"
        assert attempt.task_id != failed.task_id
        assert db.get(NortPoleWorkflowRun, attempt.id).retry_of_id == failed.id
        assert db.get(NortPoleWorkflowSchedule, schedule.id).next_run_at == schedule.next_run_at
        entries = {run.id: run for run in workflow_run_feed(user=owner, db_session=db).runs}
        assert not entries[failed.id].can_retry
        assert entries[failed.id].retry_id == attempt.id
        assert entries[attempt.id].retry_of_id == failed.id
        assert entries[attempt.id].trigger == "retry"


def test_retry_refuses_changed_workflows_and_recorded_external_actions(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as db:
        owner = db.get(User, world["ann"])
        schedule = _new(db, owner)
        with patch.object(tasks_api, "draft_plan", side_effect=PlanError("Offline")):
            failed = api.run_now(schedule.id, api.VersionOnly(version=schedule.version), user=owner, db_session=db)
        saved = db.get(NortPoleWorkflowSchedule, schedule.id)
        task = db.get(NortPoleTask, failed.task_id)
        run = db.get(NortPoleWorkflowRun, failed.id)
        task.request = "A different request"
        db.commit()
        with pytest.raises(NortPoleError, match="workflow has changed"):
            api.retry_run(schedule.id, failed.id, user=owner, db_session=db)
        db.rollback()

        task.request = saved.request
        action = NortPoleAction(
            task_id=task.id, owner_id=owner.id, target_name="Synthetic target",
            payload={}, fingerprint="a" * 64, state="executing",
        )
        db.add(action)
        db.commit()
        assert not recovery.can_retry(db, saved, run, task)
        with pytest.raises(NortPoleError, match="no longer eligible"):
            api.retry_run(schedule.id, failed.id, user=owner, db_session=db)
        db.rollback()

        db.delete(action)
        saved.version += 1
        db.commit()
        with pytest.raises(NortPoleError, match="no longer eligible"):
            api.retry_run(schedule.id, failed.id, user=owner, db_session=db)
        db.rollback()
        assert db.scalar(select(NortPoleWorkflowRun.id).where(NortPoleWorkflowRun.retry_of_id == failed.id)) is None


def test_check_outcome_recovers_committed_plan_after_worker_error(world) -> None:  # type: ignore[no-untyped-def]
    plan_task = tasks_api.plan_task

    def stop_after_plan(*args, **kwargs):
        plan_task(*args, **kwargs)
        raise RuntimeError("Worker stopped after saving the plan")

    with get_session_with_current_tenant() as db:
        owner = db.get(User, world["ann"])
        schedule = _new(db, owner)
        with (patch.object(tasks_api, "draft_plan", return_value=PLAN),
              patch.object(tasks_api, "plan_task", side_effect=stop_after_plan),
              pytest.raises(RuntimeError, match="stopped")):
            runner.fire_one(db, schedule.id, manual_version=schedule.version)

        interrupted, = api.list_runs(schedule.id, user=owner, db_session=db)
        assert interrupted.outcome == "interrupted"
        assert interrupted.task_id and interrupted.task_state == "plan_review"
        action = NortPoleAction(
            task_id=interrupted.task_id, owner_id=owner.id, target_name="Synthetic target",
            payload={}, fingerprint="a" * 64, state="executing",
        )
        db.add(action)
        db.commit()
        assert "external action still needs review" in api.check_run_outcome(
            schedule.id, interrupted.id, user=owner, db_session=db,
        ).detail
        assert db.get(NortPoleWorkflowRun, interrupted.id).outcome == "interrupted"
        db.delete(action)
        db.commit()
        assert api.check_run_outcome(schedule.id, interrupted.id, user=owner, db_session=db).detail == (
            "The saved plan was recovered."
        )
        recovered, = api.list_runs(schedule.id, user=owner, db_session=db)
        assert recovered.id == interrupted.id and recovered.outcome == "plan_ready"
        assert recovered.task_id == interrupted.task_id


def test_check_outcome_recovers_saved_expense_result_and_leaves_unknown_for_review(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as db:
        owner = db.get(User, world["ann"])
        schedule = _new(db, owner)
        review_id = _add_run(db, owner, "Expenses.csv", needs_review=True)
        review = db.get(ChatMessage, review_id)
        proven = NortPoleWorkflowRun(
            schedule_id=schedule.id, chat_session_id=review.chat_session_id, chat_result_id=review_id,
            outcome="interrupted",
        )
        unknown = NortPoleWorkflowRun(schedule_id=schedule.id, chat_session_id=review.chat_session_id, outcome="interrupted")
        db.add_all([proven, unknown])
        db.commit()

        assert "recovered" in api.check_run_outcome(schedule.id, proven.id, user=owner, db_session=db).detail
        assert proven.outcome == "needs_review"
        assert "still needs review" in api.check_run_outcome(schedule.id, unknown.id, user=owner, db_session=db).detail
        assert unknown.outcome == "interrupted"
        assert "still needs review" in unknown.reason
        with pytest.raises(NortPoleError, match="no longer eligible"):
            api.retry_run(schedule.id, unknown.id, user=owner, db_session=db)
