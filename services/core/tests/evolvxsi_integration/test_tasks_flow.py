"""Reviewed-task flow on the real database, with the real planner calling the
default model through the route policy (the sandbox default is the mock route).
"""

import uuid
from unittest.mock import patch

import pytest
import requests
from sqlalchemy import text

from evolvxsi.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant
from evolvxsi.db.models import User
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.work.tasks import api
from evolvxsi.work.tasks.models import EvolvXSITask
from evolvxsi.work.tasks.states import TaskState


def _up() -> bool:
    try:
        SqlEngine.init_engine(pool_size=2, max_overflow=0)
    except Exception:
        pass
    try:
        with get_session_with_current_tenant() as s:
            s.execute(text("select 1 from evolvxsi_task limit 1"))
        return True
    except Exception:
        return False


def _mock_model_up() -> bool:
    try:
        return requests.get("http://127.0.0.1:18001/v1/models", timeout=2).ok
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the task table")
RUN = uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
def people():  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        a = User(id=uuid.uuid4(), email=f"owner-{RUN}@example.com", hashed_password="x", is_active=True, is_verified=True)
        b = User(id=uuid.uuid4(), email=f"other-{RUN}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add_all([a, b])
        s.commit()
        ids = (a.id, b.id)
    yield ids
    with get_session_with_current_tenant() as s:
        s.query(EvolvXSITask).filter(EvolvXSITask.owner_id.in_(ids)).delete()
        s.execute(text("delete from evolvxsi_audit_event where actor_email like :p and row_hash is null"), {"p": f"%-{RUN}@example.com"})
        s.query(User).filter(User.id.in_(ids)).delete()
        s.commit()


def _user(s, uid):  # type: ignore[no-untyped-def]
    return s.get(User, uid)


def _draft(s, uid, title="Travel policy check"):  # type: ignore[no-untyped-def]
    return api.create_draft(api.TaskDraft(title=title, request="What changed in the travel policy?"), user=_user(s, uid), db_session=s)


def test_saving_a_draft_starts_nothing(people) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        t = _draft(s, people[0])
        assert t.state is TaskState.DRAFT and t.started_at is None and t.plan is None


@pytest.mark.skipif(not _mock_model_up(), reason="needs a model route (the default may be the mock or a real model)")
def test_start_drafts_a_plan_through_the_routed_model_then_accept(people) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u = _user(s, people[0])
        t = _draft(s, people[0])
        started = api.start_task(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
        assert started.state is TaskState.PLAN_REVIEW, started.plan_error
        assert started.started_at is not None
        assert 2 <= len(started.plan or []) <= 8 and all(step.strip() for step in started.plan)
        assert started.plan_route in {"local", "private", "cloud"}
        accepted = api.accept_plan(t.id, api.VersionOnly(version=started.version), user=u, db_session=s)
        assert accepted.state is TaskState.PLAN_ACCEPTED


def test_a_second_start_is_refused(people) -> None:  # type: ignore[no-untyped-def]
    from evolvxsi.work.tasks.planner import PlanResult

    with get_session_with_current_tenant() as s, patch.object(api, "draft_plan", return_value=PlanResult(["a", "b", "c"], "local")):
        u = _user(s, people[0])
        t = _draft(s, people[0])
        api.start_task(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
        with pytest.raises(EvolvXSIError):
            api.start_task(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)


def test_a_stale_version_is_refused(people) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u = _user(s, people[0])
        t = _draft(s, people[0])
        edited = api.edit_draft(t.id, api.TaskEdit(title="New title", request="r", version=t.version), user=u, db_session=s)
        assert edited.version == t.version + 1
        with pytest.raises(EvolvXSIError):
            api.edit_draft(t.id, api.TaskEdit(title="Old tab", request="r", version=t.version), user=u, db_session=s)


def test_others_cannot_see_or_change_the_task(people) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        t = _draft(s, people[0])
        other = _user(s, people[1])
        with pytest.raises(EvolvXSIError):
            api.get_task(t.id, user=other, db_session=s)
        with pytest.raises(EvolvXSIError):
            api.start_task(t.id, api.VersionOnly(version=t.version), user=other, db_session=s)
        assert t.id not in {x.id for x in api.list_tasks(user=other, db_session=s)}


def test_revise_returns_to_draft_and_keeps_the_note(people) -> None:  # type: ignore[no-untyped-def]
    from evolvxsi.work.tasks.planner import PlanResult

    with get_session_with_current_tenant() as s, patch.object(api, "draft_plan", return_value=PlanResult(["a"], "local")):
        u = _user(s, people[0])
        t = _draft(s, people[0])
        r = api.start_task(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
        back = api.revise_plan(t.id, api.Revise(version=r.version, note="Limit to 2026"), user=u, db_session=s)
        assert back.state is TaskState.DRAFT and back.revision_note == "Limit to 2026"
        # Editable again, and can be started again.
        api.edit_draft(t.id, api.TaskEdit(title="Travel 2026", request="Only 2026", version=back.version), user=u, db_session=s)


def test_a_blocked_route_fails_the_plan_without_sending(people) -> None:  # type: ignore[no-untyped-def]
    from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode

    sent = []
    blocked = EvolvXSIError(EvolvXSIErrorCode.POLICY_BLOCKED, "Cloud routes are not allowed for confidential data.")

    class FakeLLM:
        class config:  # noqa: N801
            model_configuration_id = 1

        def invoke(self, *a, **k):  # type: ignore[no-untyped-def]
            sent.append(1)

    with get_session_with_current_tenant() as s, \
         patch("evolvxsi.work.tasks.planner.get_default_llm", return_value=FakeLLM()), \
         patch("evolvxsi.work.tasks.planner.enforce_route", side_effect=blocked):
        u = _user(s, people[0])
        t = _draft(s, people[0])
        r = api.start_task(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
        assert r.state is TaskState.PLAN_FAILED
        assert "not allowed" in (r.plan_error or "")
        assert sent == [], "nothing may be sent to a blocked route"


def test_cancel(people) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u = _user(s, people[0])
        t = _draft(s, people[0])
        c = api.cancel_task(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
        assert c.state is TaskState.CANCELLED
        with pytest.raises(EvolvXSIError):
            api.start_task(t.id, api.VersionOnly(version=c.version), user=u, db_session=s)
