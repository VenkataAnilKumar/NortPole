"""The administrator audit view: filters, paging, and who may read it."""

import uuid

import pytest
from sqlalchemy import text

from evolvxsi.audit_log import api as audit_api
from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from tests.evolvxsi_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")
RUN = uuid.uuid4().hex[:8]
ACTOR_A, ACTOR_B = f"audit-a-{RUN}@example.com", f"audit-b-{RUN}@example.com"


@pytest.fixture(scope="module")
def rows():  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        for i in range(7):
            s.execute(
                text("insert into evolvxsi_audit_event (action, outcome, actor_email, summary) values (:a, :o, :e, :m)"),
                {"a": "task.start" if i % 2 == 0 else "action.execute", "o": "denied" if i == 3 else "success",
                 "e": ACTOR_A if i < 5 else ACTOR_B, "m": f"event {i} 100% done_{RUN}"},
            )
        s.commit()
    yield
    with get_session_with_current_tenant() as s:
        s.execute(text("delete from evolvxsi_audit_event where actor_email in (:a, :b)"), {"a": ACTOR_A, "b": ACTOR_B})
        s.commit()


def _call(s, **kw):  # type: ignore[no-untyped-def]
    args = dict(limit=50, before_id=None, action_prefix=None, outcome=None, actor=None, _=None, db_session=s)
    args.update(kw)
    return audit_api.list_events(**args)


def test_filters_by_actor_outcome_and_action_prefix(rows) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        assert len(_call(s, actor=f"audit-a-{RUN}").events) == 5
        assert len(_call(s, actor=f"audit-b-{RUN}").events) == 2
        assert [e.outcome for e in _call(s, actor=RUN, outcome="denied").events] == ["denied"]
        task_only = _call(s, actor=RUN, action_prefix="task.").events
        assert task_only and all(e.action.startswith("task.") for e in task_only)


def test_paging_covers_every_row_once_newest_first(rows) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        seen: list[int] = []
        cursor = None
        while True:
            page = _call(s, actor=RUN, limit=3, before_id=cursor)
            seen += [e.id for e in page.events]
            if page.next_before_id is None:
                break
            cursor = page.next_before_id
        assert len(seen) == 7 and len(set(seen)) == 7 and seen == sorted(seen, reverse=True)


def test_search_wildcards_mean_themselves(rows) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        assert len(_call(s, actor="%").events) == 0, "a percent sign must not match every actor"
        assert len(_call(s, actor="_").events) == 0, "an underscore must not match any single character"


def test_the_action_list_for_the_filter_is_returned(rows) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        assert {"task.start", "action.execute"} <= set(_call(s, actor=RUN).actions)
