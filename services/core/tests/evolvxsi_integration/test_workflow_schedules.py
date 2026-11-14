"""Scheduled workflows on the real database: off until enabled, a run stops at the plan, a newer plan replaces a
waiting one, the accept wins a race, auto-pause after three, skips, owner checks, claiming, and the audit."""

import datetime
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.models import Notification, User
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.tasks import api as tasks_api
from evolvxsi.tasks.models import EvolvXSITask
from evolvxsi.tasks.planner import PlanError, PlanResult
from evolvxsi.workflow_schedules import api, controls, runner
from evolvxsi.workflow_schedules.models import EvolvXSIWorkflowRun, EvolvXSIWorkflowSchedule
from tests.evolvxsi_integration.test_tasks_flow import _up

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
        s.query(EvolvXSIWorkflowSchedule).filter(EvolvXSIWorkflowSchedule.owner_id.in_(ids.values())).delete(synchronize_session=False)
        s.query(EvolvXSITask).filter(EvolvXSITask.owner_id.in_(ids.values())).delete(synchronize_session=False)
        s.query(Notification).filter(Notification.user_id.in_(ids.values())).delete(synchronize_session=False)
        s.execute(text("delete from evolvxsi_audit_event where actor_email like :p and row_hash is null"), {"p": f"sched-%-{TAG}@example.com"})
        s.query(User).filter(User.id.in_(ids.values())).delete(synchronize_session=False)
        s.commit()


def _new(s, user, **kw):  # type: ignore[no-untyped-def]
    body = dict(name="Weekly travel check", title="Travel check", request=REQUEST, cadence="daily", at_time="08:30", timezone="Europe/London")
    body.update(kw)
    return api.create_schedule(api.NewSchedule(**body), user=user, db_session=s)


def _due(s, sid) -> None:  # type: ignore[no-untyped-def]
    s.query(EvolvXSIWorkflowSchedule).filter_by(id=sid).update({"next_run_at": NOW - datetime.timedelta(minutes=1)})
    s.commit()


def _fire(s, sid, plan=PLAN):  # type: ignore[no-untyped-def]
    _due(s, sid)
    assert sid in runner.claim_due(s, NOW)
    with patch.object(tasks_api, "draft_plan", return_value=plan) if not isinstance(plan, Exception) else patch.object(tasks_api, "draft_plan", side_effect=plan):
        return runner.fire_one(s, sid)


def test_scheduling_is_off_until_an_administrator_turns_it_on(world) -> None:  # type: ignore[no-untyped-def]
    controls.save(controls.ScheduleControls(enabled=False))
    with get_session_with_current_tenant() as s:
        with pytest.raises(EvolvXSIError):
            _new(s, s.get(User, world["ann"]))
        assert controls.load().enabled is False
        controls.save(controls.ScheduleControls(enabled=True, groups=[f"no-such-group-{TAG}"]))
        with pytest.raises(EvolvXSIError):
            _new(s, s.get(User, world["ann"]))
        assert api.list_mine(user=s.get(User, world["ann"]), db_session=s).scheduling_allowed is False


def test_a_run_drafts_the_plan_as_the_owner_and_stops(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        v = _new(s, ann)
        assert v.when == "Every day at 08:30 (Europe/London)" and v.next_run_at is not None
        run = _fire(s, v.id)
        assert (run.outcome, run.route_kind, run.input_tokens, run.output_tokens) == ("plan_ready", "local", 120, 30)
        task = s.get(EvolvXSITask, run.task_id)
        assert (task.state, task.owner_id, task.schedule_id, task.plan) == ("plan_review", ann.id, v.id, ["Find the policy", "Summarise"])
        listed = next(t for t in tasks_api.list_tasks(user=ann, db_session=s) if t.id == task.id)
        assert listed.schedule_name == "Weekly travel check", "Inbox can label it"
        sched = s.get(EvolvXSIWorkflowSchedule, v.id)
        assert sched.next_run_at > NOW and sched.state == "active", "no catch-up: the next time after now"
        assert not runner.claim_due(s, NOW), "claimed once"
        audit = s.execute(text("select action, details::text, summary from evolvxsi_audit_event where resource_id = :r"), {"r": str(v.id)}).all()
        assert {a for a, _, _ in audit} >= {"schedule.change", "schedule.fire"}
        assert all(TAG not in (d or "") and TAG not in sm for _, d, sm in audit), "no request text in the audit"


def test_a_newer_plan_replaces_a_waiting_one_and_three_unaccepted_pause(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        v = _new(s, ann)
        first = _fire(s, v.id)
        second = _fire(s, v.id)
        assert s.get(EvolvXSITask, first.task_id).state == "superseded"
        assert s.get(EvolvXSIWorkflowSchedule, v.id).unaccepted_streak == 1
        third = _fire(s, v.id)
        assert s.get(EvolvXSITask, second.task_id).state == "superseded"
        fourth = _fire(s, v.id)
        sched = s.get(EvolvXSIWorkflowSchedule, v.id)
        assert (fourth.outcome, sched.state, sched.pause_reason) == ("paused", "paused", "unaccepted")
        assert s.get(EvolvXSITask, third.task_id).state == "plan_review", "the third plan stays waiting"
        note = s.query(Notification).filter_by(user_id=ann.id).one()
        assert note.title == 'Scheduled workflow "Weekly travel check" was paused' and "3 plans" in note.description
        assert not runner.claim_due(s, NOW + datetime.timedelta(days=30)), "a paused schedule never fires"
        resumed = api.resume_schedule(v.id, api.VersionOnly(version=sched.version), user=ann, db_session=s)
        assert resumed.state == "active" and s.get(EvolvXSIWorkflowSchedule, v.id).unaccepted_streak == 0


def test_accepting_a_plan_resets_the_count_and_an_accept_wins_the_race(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        v = _new(s, ann)
        _fire(s, v.id)
        r2 = _fire(s, v.id)
        assert s.get(EvolvXSIWorkflowSchedule, v.id).unaccepted_streak == 1
        t2 = s.get(EvolvXSITask, r2.task_id)
        tasks_api.accept_plan(t2.id, tasks_api.VersionOnly(version=t2.version), user=ann, db_session=s)
        _fire(s, v.id)
        assert s.get(EvolvXSITask, t2.id).state == "plan_accepted", "an accepted plan is never replaced"
        assert s.get(EvolvXSIWorkflowSchedule, v.id).unaccepted_streak == 0


def test_failures_and_inactive_packs_are_skipped_and_three_pause(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        v = _new(s, ann)
        r = _fire(s, v.id, plan=PlanError("No plan"))
        assert (r.outcome, s.get(EvolvXSITask, r.task_id).state) == ("plan_failed", "plan_failed")
        s.query(EvolvXSIWorkflowSchedule).filter_by(id=v.id).update({"pack_id": f"gone-{TAG}", "pack_template": "x"})
        s.commit()
        r = _fire(s, v.id)
        assert (r.outcome, r.task_id) == ("skipped", None) and "no longer active" in r.reason
        _fire(s, v.id)
        sched = s.get(EvolvXSIWorkflowSchedule, v.id)
        assert (sched.state, sched.pause_reason) == ("paused", "skipped")


def test_scheduling_turned_off_or_an_inactive_owner_pauses_at_the_next_run(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann, bob = s.get(User, world["ann"]), s.get(User, world["bob"])
        va, vb = _new(s, ann), _new(s, bob)
        controls.save(controls.ScheduleControls(enabled=False))
        assert _fire(s, va.id).outcome == "paused"
        assert s.get(EvolvXSIWorkflowSchedule, va.id).pause_reason == "scheduling_off"
        controls.save(controls.ScheduleControls(enabled=True))
        bob.is_active = False
        s.commit()
        assert _fire(s, vb.id).outcome == "paused"
        assert s.get(EvolvXSIWorkflowSchedule, vb.id).pause_reason == "owner_inactive"
        assert not s.query(EvolvXSITask).filter_by(owner_id=bob.id).count(), "nothing is planned for an inactive owner"


def test_people_only_see_and_change_their_own_and_administrators_can_pause_any(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann, bob, admin = s.get(User, world["ann"]), s.get(User, world["bob"]), s.get(User, world["admin"])
        v = _new(s, ann)
        assert not api.list_mine(user=bob, db_session=s).schedules
        for call in (lambda: api.pause_schedule(v.id, api.VersionOnly(version=v.version), user=bob, db_session=s),
                     lambda: api.list_runs(v.id, user=bob, db_session=s),
                     lambda: api.delete_schedule(v.id, user=bob, db_session=s)):
            with pytest.raises(EvolvXSIError):
                call()
        row = next(x for x in api.list_all(_=admin, db_session=s) if x.id == v.id)
        assert row.owner_email == ann.email and REQUEST not in row.model_dump_json(), "administrators never see the request"
        assert api.admin_pause(v.id, user=admin, db_session=s).state == "paused"
        assert s.query(Notification).filter_by(user_id=ann.id).count() == 1


def test_limits_and_validation(world) -> None:  # type: ignore[no-untyped-def]
    controls.save(controls.ScheduleControls(enabled=True, max_per_person=1))
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        with pytest.raises(EvolvXSIError):
            _new(s, ann, cadence="hourly")
        with pytest.raises(EvolvXSIError):
            _new(s, ann, cadence="once", run_on=datetime.date(2020, 1, 1))
        _new(s, ann)
        with pytest.raises(EvolvXSIError):
            _new(s, ann)


def test_sharing_with_own_groups_and_copying_runs_as_the_copier(world) -> None:  # type: ignore[no-untyped-def]
    from evolvxsi.db.models import User__UserGroup, UserGroup

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
            with pytest.raises(EvolvXSIError):
                api.share_schedule(v.id, api.ShareBody(version=v.version, groups=[other.name]), user=ann, db_session=s)
            shared = api.share_schedule(v.id, api.ShareBody(version=v.version, groups=[team.name]), user=ann, db_session=s)
            assert shared.shared_with_groups == [team.name]
            seen = api.list_shared(user=bob, db_session=s)
            assert [x.id for x in seen] == [v.id] and seen[0].owner_email == ann.email and not seen[0].already_copied
            assert not api.list_shared(user=admin, db_session=s), "only members of a shared group see it"
            with pytest.raises(EvolvXSIError):
                api.copy_schedule(v.id, user=admin, db_session=s)
            copy = api.copy_schedule(v.id, user=bob, db_session=s)
            assert copy.copied_from_id == v.id and copy.when == v.when and copy.shared_with_groups == []
            assert api.list_shared(user=bob, db_session=s)[0].already_copied
            run = _fire(s, copy.id)
            task = s.get(EvolvXSITask, run.task_id)
            assert task.owner_id == bob.id, "a copy runs as the person who copied it"
            assert not s.query(EvolvXSITask).filter_by(owner_id=ann.id).count(), "the original owner gets nothing"
        finally:
            s.query(User__UserGroup).filter(User__UserGroup.user_group_id.in_([team.id, other.id])).delete(synchronize_session=False)
            s.query(UserGroup).filter(UserGroup.id.in_([team.id, other.id])).delete(synchronize_session=False)
            s.commit()


def test_quality_counts_scheduled_runs_and_acceptances(world) -> None:  # type: ignore[no-untyped-def]
    from evolvxsi.quality.api import _scheduled

    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
        before = _scheduled(s, since)
        v = _new(s, ann)
        r1 = _fire(s, v.id)
        t1 = s.get(EvolvXSITask, r1.task_id)
        tasks_api.accept_plan(t1.id, tasks_api.VersionOnly(version=t1.version), user=ann, db_session=s)
        _fire(s, v.id)
        after = _scheduled(s, since)
        assert after["runs"] - before["runs"] == 2 and after["plans"] - before["plans"] == 2
        assert after["accepted"] - before["accepted"] == 1
        assert after["input_tokens"] - before["input_tokens"] == 240 and after["output_tokens"] - before["output_tokens"] == 60
