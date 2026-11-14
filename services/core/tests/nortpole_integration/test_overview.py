"""The admin overview counts what needs attention and never shows anyone's task text."""

import datetime
import json
import uuid

import pytest

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.insight.overview.api import build
from nortpole.governance.route_policy.audit import NortPoleAuditEvent
from nortpole.work.tasks.models import NortPoleTask
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]
SECRET_TITLE = f"Quarterly layoffs plan {TAG}"


def test_failures_and_refusals_are_counted_without_task_titles() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    with get_session_with_current_tenant() as s:
        owner = s.query(User).first()
        before = build(s, now)
        t = NortPoleTask(owner_id=owner.id, title=SECRET_TITLE, request=f"secret request {TAG}", state="run_failed", version=1,
                         run_error="The model route is blocked for this data class.")
        a = NortPoleAuditEvent(action="route.blocked", outcome="denied", summary=f"Refused {TAG}")
        s.add_all([t, a]); s.commit()
        try:
            after = build(s, now + datetime.timedelta(seconds=1))
            assert after["runs"]["failed_runs"] == before["runs"]["failed_runs"] + 1
            assert any(e["error"].startswith("The model route is blocked") for e in after["runs"]["recent_errors"])
            assert after["refusals"]["total"] == before["refusals"]["total"] + 1
            text = json.dumps(after)
            assert SECRET_TITLE not in text and f"secret request {TAG}" not in text, "no task title or request reaches the overview"
            assert {"setup", "packs", "audit_chain"} <= set(after) and len(after["setup"]) == 6
            assert all({"item", "ok", "note", "href"} <= set(x) for x in after["setup"])
        finally:
            s.delete(s.get(NortPoleTask, t.id)); s.commit()
