"""Scheduled workflows on the real database: off until enabled, a run stops at the plan, a newer plan replaces a
waiting one, the accept wins a race, auto-pause after three, skips, owner checks, claiming, and the audit."""

import datetime
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from nortpole.configs.constants import NotificationType
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import Notification, User
from nortpole.db.notification import InboxTab, get_notifications
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.redis.lock_context import redis_shared_lock
from nortpole.work.tasks import api as tasks_api
from nortpole.work.tasks.models import NortPoleTask
from nortpole.work.tasks.planner import PlanError, PlanResult
from nortpole.work.tasks.states import TaskAction
from nortpole.work.workflow_schedules import api, controls, runner
from nortpole.work.workflow_schedules.models import NortPoleWorkflowRun, NortPoleWorkflowSchedule
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]
REQUEST = f"Summarise the travel policy changes {TAG}"
NOW = datetime.datetime.now(datetime.timezone.utc)
PLAN = PlanResult(["Find the policy", "Summarise"], "local", input_tokens=120, output_tokens=30)


@pytest.fixture()
def world():  # type: ignore[no-untyped-def]
    saved = controls.load()
    controls.save(controls.ScheduleControls(version=saved.version + 1, enabled=True))
    with get_session_with_current_tenant() as s:
        people = [User(id=uuid.uuid4(), email=f"sched-{n}-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True) for n in ("ann", "bob", "admin")]
        s.add_all(people)
        s.commit()
        ids = {"ann": people[0].id, "bob": people[1].id, "admin": people[2].id}
    yield ids
    controls.save(saved)
    with get_session_with_current_tenant() as s:
        s.query(NortPoleWorkflowSchedule).filter(NortPoleWorkflowSchedule.owner_id.in_(ids.values())).delete(synchronize_session=False)
        s.query(NortPoleTask).filter(NortPoleTask.owner_id.in_(ids.values())).delete(synchronize_session=False)
        s.query(Notification).filter(Notification.user_id.in_(ids.values())).delete(synchronize_session=False)
        s.execute(text("delete from nortpole_audit_event where actor_email like :p and row_hash is null"), {"p": f"sched-%-{TAG}@example.com"})
        s.query(User).filter(User.id.in_(ids.values())).delete(synchronize_session=False)
        s.commit()


def _new(s, user, **kw):  # type: ignore[no-untyped-def]
    body = dict(name="Weekly travel check", title="Travel check", request=REQUEST, cadence="daily", at_time="08:30", timezone="Europe/London")
    body.update(kw)
    return api.create_schedule(api.NewSchedule(**body), user=user, db_session=s)


def _due(s, sid) -> None:  # type: ignore[no-untyped-def]
    s.query(NortPoleWorkflowSchedule).filter_by(id=sid).update({"next_run_at": NOW - datetime.timedelta(minutes=1)})
    s.commit()


def _fire(s, sid, plan=PLAN):  # type: ignore[no-untyped-def]
    _due(s, sid)
    run_id = next(run_id for run_id in runner.claim_due(s, NOW)
                  if s.get(NortPoleWorkflowRun, run_id).schedule_id == sid)
    with patch.object(tasks_api, "draft_plan", return_value=plan) if not isinstance(plan, Exception) else patch.object(tasks_api, "draft_plan", side_effect=plan):
        return runner.fire_one(s, sid, run_id=run_id)


def test_scheduling_is_off_until_an_administrator_turns_it_on(world) -> None:  # type: ignore[no-untyped-def]
    controls.save(controls.ScheduleControls(enabled=False))
    with get_session_with_current_tenant() as s:
        with pytest.raises(NortPoleError):
            _new(s, s.get(User, world["ann"]))
        assert controls.load().enabled is False
        controls.save(controls.ScheduleControls(enabled=True, groups=[f"no-such-group-{TAG}"]))
        with pytest.raises(NortPoleError):
            _new(s, s.get(User, world["ann"]))
        assert api.list_mine(user=s.get(User, world["ann"]), db_session=s).scheduling_allowed is False


def test_a_run_drafts_the_plan_as_the_owner_and_stops(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        v = _new(s, ann)
        assert v.when == "Every day at 08:30 (Europe/London)" and v.next_run_at is not None
        run = _fire(s, v.id)
        assert (run.outcome, run.route_kind, run.input_tokens, run.output_tokens) == ("plan_ready", "local", 120, 30)
        task = s.get(NortPoleTask, run.task_id)
        assert (task.state, task.owner_id, task.schedule_id, task.plan) == ("plan_review", ann.id, v.id, ["Find the policy", "Summarise"])
        listed = next(t for t in tasks_api.list_tasks(user=ann, db_session=s) if t.id == task.id)
        assert listed.schedule_name == "Weekly travel check", "Inbox can label it"
        sched = s.get(NortPoleWorkflowSchedule, v.id)
        assert sched.next_run_at > NOW and sched.state == "active", "no catch-up: the next time after now"
        assert not runner.claim_due(s, NOW), "claimed once"
        audit = s.execute(text("select action, details::text, summary from nortpole_audit_event where resource_id = :r"), {"r": str(v.id)}).all()
        assert {a for a, _, _ in audit} >= {"schedule.change", "schedule.fire"}
        assert all(TAG not in (d or "") and TAG not in sm for _, d, sm in audit), "no request text in the audit"


def test_timer_saves_a_run_before_execution_and_recovers_it_on_the_next_tick(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        owner = s.get(User, world["ann"])
        schedule = _new(s, owner)
        _due(s, schedule.id)
        run_id = next(rid for rid in runner.claim_due(s, NOW)
                      if s.get(NortPoleWorkflowRun, rid).schedule_id == schedule.id)
        assert s.get(NortPoleWorkflowSchedule, schedule.id).next_run_at > NOW
        run = s.get(NortPoleWorkflowRun, run_id)
        assert (run.trigger, run.outcome, run.started_at) == ("timer", "queued", None)
        s.commit()
        with get_session_with_current_tenant() as worker, patch.object(tasks_api, "draft_plan", return_value=PLAN):
            assert runner.fire_one(worker, schedule.id, run_id=run_id).outcome == "plan_ready"
        s.refresh(run)
        assert run.outcome == "plan_ready" and run.task_id is not None
        assert run.fired_at <= run.started_at <= run.completed_at
        assert runner.fire_one(s, schedule.id, run_id=run_id) is None


def test_a_newer_plan_replaces_a_waiting_one_and_three_unaccepted_pause(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        v = _new(s, ann)
        first = _fire(s, v.id)
        second = _fire(s, v.id)
        assert s.get(NortPoleTask, first.task_id).state == "superseded"
        assert s.get(NortPoleWorkflowSchedule, v.id).unaccepted_streak == 1
        third = _fire(s, v.id)
        assert s.get(NortPoleTask, second.task_id).state == "superseded"
        fourth = _fire(s, v.id)
        sched = s.get(NortPoleWorkflowSchedule, v.id)
        assert (fourth.outcome, sched.state, sched.pause_reason) == ("paused", "paused", "unaccepted")
        assert s.get(NortPoleTask, third.task_id).state == "plan_review", "the third plan stays waiting"
        note = s.query(Notification).filter_by(user_id=ann.id).one()
        assert note.title == 'Scheduled workflow "Weekly travel check" was paused' and "3 plans" in note.description
        assert not runner.claim_due(s, NOW + datetime.timedelta(days=30)), "a paused schedule never fires"
        resumed = api.resume_schedule(v.id, api.VersionOnly(version=sched.version), user=ann, db_session=s)
        assert resumed.state == "active" and s.get(NortPoleWorkflowSchedule, v.id).unaccepted_streak == 0


def test_save_and_prepare_a_plan_keeps_the_future_schedule(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        owner = s.get(User, world["ann"])
        with patch.object(tasks_api, "draft_plan", return_value=PLAN):
            saved = _new(s, owner, prepare_now=True, notify_plan_ready=True)

        assert saved.initial_plan is not None
        assert saved.initial_plan.outcome == "plan_ready"
        assert saved.next_run_at is not None and saved.next_run_at > datetime.datetime.now(datetime.timezone.utc)
        task = s.get(NortPoleTask, saved.initial_plan.task_id)
        assert task is not None
        assert (task.owner_id, task.schedule_id, task.state) == (owner.id, saved.id, "plan_review")
        assert saved.state == "active"
        notification = s.query(Notification).filter_by(
            user_id=owner.id, notif_type=NotificationType.WORKFLOW_PLAN_READY,
        ).one()
        assert notification.additional_data["run_id"] == str(saved.initial_plan.id)


def test_first_plan_failure_still_returns_the_saved_schedule(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        owner = s.get(User, world["ann"])
        with patch.object(tasks_api, "draft_plan", side_effect=PlanError("Model unavailable")):
            saved = _new(s, owner, prepare_now=True)

        assert saved.initial_plan is not None
        assert (saved.initial_plan.outcome, saved.initial_plan.reason) == ("plan_failed", "Model unavailable")
        assert saved.next_run_at is not None and saved.state == "active"
        notification = s.query(Notification).filter_by(
            user_id=owner.id, notif_type=NotificationType.WORKFLOW_RUN_FAILED,
        ).one()
        assert notification.description == "Model unavailable"
        assert notification.additional_data["link"] == (
            f"/app/workflows/scheduled?schedule={saved.id}&run={saved.initial_plan.id}"
        )
        with patch.object(tasks_api, "draft_plan", side_effect=PlanError("Another failure")):
            muted = _new(s, owner, prepare_now=True, notify_run_failed=False)
        assert muted.initial_plan.outcome == "plan_failed"
        assert s.query(Notification).filter_by(
            user_id=owner.id, notif_type=NotificationType.WORKFLOW_RUN_FAILED,
        ).count() == 1


def test_owner_can_run_now_and_find_the_plan_without_moving_the_schedule(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        owner = s.get(User, world["ann"])
        schedule = _new(s, owner)

        def observe_running(*_args, **_kwargs):
            with get_session_with_current_tenant() as observer:
                run = observer.query(NortPoleWorkflowRun).filter_by(schedule_id=schedule.id).one()
                assert (run.trigger, run.outcome, run.schedule_version) == ("manual", "running", schedule.version)
                assert run.started_at and run.completed_at is None
            return PLAN

        with patch.object(tasks_api, "draft_plan", side_effect=observe_running):
            run = api.run_now(schedule.id, api.VersionOnly(version=schedule.version), user=owner, db_session=s)

        assert run.outcome == "plan_ready"
        task = s.get(NortPoleTask, run.task_id)
        assert (task.owner_id, task.schedule_id, task.state) == (owner.id, schedule.id, "plan_review")
        assert s.get(NortPoleWorkflowSchedule, schedule.id).next_run_at == schedule.next_run_at
        assert api.list_runs(schedule.id, user=owner, db_session=s)[0].id == run.id


def test_run_now_rejects_other_users_stale_versions_and_paused_schedules(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        owner = s.get(User, world["ann"])
        other = s.get(User, world["bob"])
        schedule = _new(s, owner)
        version = api.VersionOnly(version=schedule.version)

        with pytest.raises(NortPoleError) as exc:
            api.run_now(schedule.id, version, user=other, db_session=s)
        assert exc.value.error_code == NortPoleErrorCode.NOT_FOUND
        with pytest.raises(NortPoleError, match="has changed"):
            api.run_now(schedule.id, api.VersionOnly(version=0), user=owner, db_session=s)
        controls.save(controls.ScheduleControls(enabled=False))
        with pytest.raises(NortPoleError, match="not turned on"):
            api.run_now(schedule.id, version, user=owner, db_session=s)
        controls.save(controls.ScheduleControls(enabled=True))
        paused = api.pause_schedule(schedule.id, version, user=owner, db_session=s)
        with pytest.raises(NortPoleError, match="no longer active"):
            api.run_now(schedule.id, api.VersionOnly(version=paused.version), user=owner, db_session=s)
        assert not api.list_runs(schedule.id, user=owner, db_session=s)


def test_run_now_rejects_overlap_with_an_existing_run(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        owner = s.get(User, world["ann"])
        schedule = _new(s, owner)
        lock_name = f"workflow_schedule:{runner.get_current_tenant_id()}:{schedule.id}"
        with redis_shared_lock(lock_name, max_time_lock_held_s=15, wait_for_lock_s=1, logger=runner.logger):
            with pytest.raises(NortPoleError, match="already running"):
                api.run_now(schedule.id, api.VersionOnly(version=schedule.version), user=owner, db_session=s)
        assert not api.list_runs(schedule.id, user=owner, db_session=s)


def test_accepted_scheduled_plan_reports_task_failure_and_successful_retry(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        owner = s.get(User, world["ann"])
        schedule = _new(s, owner, notify_run_complete=True, notify_plan_ready=True)
        run = _fire(s, schedule.id)
        task = s.get(NortPoleTask, run.task_id)
        plan_version = task.version
        task = tasks_api._move(s, task.id, owner, plan_version, TaskAction.ACCEPT)
        with pytest.raises(NortPoleError):
            tasks_api._move(s, task.id, owner, plan_version, TaskAction.ACCEPT)
        task = tasks_api._move(s, task.id, owner, task.version, TaskAction.RUN)
        task = tasks_api._move(s, task.id, owner, task.version, TaskAction.RUN_FAILED, run_error="Search unavailable")
        failed_version = task.version
        task = tasks_api._move(s, task.id, owner, task.version, TaskAction.RUN)
        task = tasks_api._move(s, task.id, owner, task.version, TaskAction.DRAFT_DONE)
        failure = s.query(Notification).filter_by(user_id=owner.id, notif_type=NotificationType.WORKFLOW_RUN_FAILED).one()
        complete = s.query(Notification).filter_by(user_id=owner.id, notif_type=NotificationType.WORKFLOW_RUN_COMPLETE).one()
        assert failure.description == "Search unavailable"
        assert failure.additional_data["task_version"] == failed_version
        assert complete.additional_data["task_version"] == task.version
        assert complete.additional_data["run_id"] == str(run.id)
        assert complete.additional_data["link"] == f"/app/workflows/drafts?task={task.id}"
        draft_version = task.version
        task = tasks_api._move(s, task.id, owner, draft_version, TaskAction.APPROVE)

        history = get_notifications(owner, s, inbox_tab=InboxTab.HISTORY)
        assert len(history) == 4
        receipts = [n for n in history if n.notif_type == NotificationType.WORKFLOW_DECISION_RECORDED]
        assert {(n.additional_data["decision"], n.additional_data["task_version"]) for n in receipts} == {
            (TaskAction.ACCEPT.value, plan_version),
            (TaskAction.APPROVE.value, draft_version),
        }
        assert {n.additional_data["task_id"] for n in receipts} == {str(task.id)}
        assert all(n.notif_type != NotificationType.WORKFLOW_DECISION_RECORDED for n in get_notifications(owner, s))
        assert [n.id for n in get_notifications(owner, s, inbox_tab=InboxTab.UPDATES)] == [failure.id]


def test_accepting_a_plan_resets_the_count_and_an_accept_wins_the_race(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        v = _new(s, ann)
        _fire(s, v.id)
        r2 = _fire(s, v.id)
        assert s.get(NortPoleWorkflowSchedule, v.id).unaccepted_streak == 1
        t2 = s.get(NortPoleTask, r2.task_id)
        tasks_api.accept_plan(t2.id, tasks_api.VersionOnly(version=t2.version), user=ann, db_session=s)
        _fire(s, v.id)
        assert s.get(NortPoleTask, t2.id).state == "plan_accepted", "an accepted plan is never replaced"
        assert s.get(NortPoleWorkflowSchedule, v.id).unaccepted_streak == 0


def test_failures_and_inactive_packs_are_skipped_and_three_pause(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        v = _new(s, ann)
        r = _fire(s, v.id, plan=PlanError("No plan"))
        assert (r.outcome, s.get(NortPoleTask, r.task_id).state) == ("plan_failed", "plan_failed")
        s.query(NortPoleWorkflowSchedule).filter_by(id=v.id).update({"pack_id": f"gone-{TAG}", "pack_template": "x"})
        s.commit()
        r = _fire(s, v.id)
        assert (r.outcome, r.task_id) == ("skipped", None) and "no longer active" in r.reason
        _fire(s, v.id)
        sched = s.get(NortPoleWorkflowSchedule, v.id)
        assert (sched.state, sched.pause_reason) == ("paused", "skipped")


def test_scheduling_turned_off_or_an_inactive_owner_pauses_at_the_next_run(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann, bob = s.get(User, world["ann"]), s.get(User, world["bob"])
        va, vb = _new(s, ann), _new(s, bob)
        controls.save(controls.ScheduleControls(enabled=False))
        assert _fire(s, va.id).outcome == "paused"
        assert s.get(NortPoleWorkflowSchedule, va.id).pause_reason == "scheduling_off"
        controls.save(controls.ScheduleControls(enabled=True))
        bob.is_active = False
        s.commit()
        assert _fire(s, vb.id).outcome == "paused"
        assert s.get(NortPoleWorkflowSchedule, vb.id).pause_reason == "owner_inactive"
        assert not s.query(NortPoleTask).filter_by(owner_id=bob.id).count(), "nothing is planned for an inactive owner"


def test_people_only_see_and_change_their_own_and_administrators_can_pause_any(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann, bob, admin = s.get(User, world["ann"]), s.get(User, world["bob"]), s.get(User, world["admin"])
        v = _new(s, ann)
        assert not api.list_mine(user=bob, db_session=s).schedules
        for call in (lambda: api.pause_schedule(v.id, api.VersionOnly(version=v.version), user=bob, db_session=s),
                     lambda: api.list_runs(v.id, user=bob, db_session=s),
                     lambda: api.delete_schedule(v.id, user=bob, db_session=s)):
            with pytest.raises(NortPoleError):
                call()
        row = next(x for x in api.list_all(_=admin, db_session=s) if x.id == v.id)
        assert row.owner_email == ann.email and REQUEST not in row.model_dump_json(), "administrators never see the request"
        assert api.admin_pause(v.id, user=admin, db_session=s).state == "paused"
        assert s.query(Notification).filter_by(user_id=ann.id).count() == 1


def test_limits_and_validation(world) -> None:  # type: ignore[no-untyped-def]
    controls.save(controls.ScheduleControls(enabled=True, max_per_person=1))
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        with pytest.raises(NortPoleError):
            _new(s, ann, cadence="hourly")
        with pytest.raises(NortPoleError):
            _new(s, ann, cadence="once", run_on=datetime.date(2020, 1, 1))
        _new(s, ann)
        with pytest.raises(NortPoleError):
            _new(s, ann)


def test_sharing_with_own_groups_and_copying_runs_as_the_copier(world) -> None:  # type: ignore[no-untyped-def]
    from nortpole.db.models import User__UserGroup, UserGroup

    with get_session_with_current_tenant() as s:
        ann, bob, admin = s.get(User, world["ann"]), s.get(User, world["bob"]), s.get(User, world["admin"])
        team, other = UserGroup(name=f"sched-team-{TAG}", is_up_to_date=True), UserGroup(name=f"sched-other-{TAG}", is_up_to_date=True)
        s.add_all([team, other])
        s.flush()
        s.add_all([User__UserGroup(user_id=ann.id, user_group_id=team.id), User__UserGroup(user_id=bob.id, user_group_id=team.id)])
        s.commit()
        try:
            v = _new(s, ann)
            assert api.list_mine(user=ann, db_session=s).my_groups == [team.name]
            with pytest.raises(NortPoleError):
                api.share_schedule(v.id, api.ShareBody(version=v.version, groups=[other.name]), user=ann, db_session=s)
            shared = api.share_schedule(v.id, api.ShareBody(version=v.version, groups=[team.name]), user=ann, db_session=s)
            assert shared.shared_with_groups == [team.name]
            seen = api.list_shared(user=bob, db_session=s)
            assert [x.id for x in seen] == [v.id] and seen[0].owner_email == ann.email and not seen[0].already_copied
            assert not api.list_shared(user=admin, db_session=s), "only members of a shared group see it"
            with pytest.raises(NortPoleError):
                api.copy_schedule(v.id, user=admin, db_session=s)
            copy = api.copy_schedule(v.id, user=bob, db_session=s)
            assert copy.copied_from_id == v.id and copy.when == v.when and copy.shared_with_groups == []
            assert api.list_shared(user=bob, db_session=s)[0].already_copied
            run = _fire(s, copy.id)
            task = s.get(NortPoleTask, run.task_id)
            assert task.owner_id == bob.id, "a copy runs as the person who copied it"
            assert not s.query(NortPoleTask).filter_by(owner_id=ann.id).count(), "the original owner gets nothing"
        finally:
            s.query(User__UserGroup).filter(User__UserGroup.user_group_id.in_([team.id, other.id])).delete(synchronize_session=False)
            s.query(UserGroup).filter(UserGroup.id.in_([team.id, other.id])).delete(synchronize_session=False)
            s.commit()


def test_quality_counts_scheduled_runs_and_acceptances(world) -> None:  # type: ignore[no-untyped-def]
    from nortpole.insight.quality.api import _scheduled

    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
        before = _scheduled(s, since)
        v = _new(s, ann)
        r1 = _fire(s, v.id)
        t1 = s.get(NortPoleTask, r1.task_id)
        tasks_api.accept_plan(t1.id, tasks_api.VersionOnly(version=t1.version), user=ann, db_session=s)
        _fire(s, v.id)
        after = _scheduled(s, since)
        assert after["runs"] - before["runs"] == 2 and after["plans"] - before["plans"] == 2
        assert after["accepted"] - before["accepted"] == 1
        assert after["input_tokens"] - before["input_tokens"] == 240 and after["output_tokens"] - before["output_tokens"] == 60
