"""Retention, legal hold, pruning and audit export on the real database."""

import csv
import datetime
import io
import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from nortpole.governance.audit_log import api as audit_api
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.redaction.request import NortPoleRedactionCount
from nortpole.governance.retention import api as ret_api
from nortpole.governance.retention.prune import prune
from nortpole.governance.retention.settings import Retention, load, save
from nortpole.governance.route_policy.audit import NortPoleAuditEvent
from nortpole.governance.route_policy.usage import NortPoleRouteUsage
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the retention tables")

TAG = f"ret-{uuid.uuid4().hex[:8]}"
ADMIN = SimpleNamespace(id=uuid.uuid4(), email=f"{TAG}@example.com")
NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture(autouse=True)
def _restore():  # type: ignore[no-untyped-def]
    original = load()
    yield
    save(original)
    with get_session_with_current_tenant() as s:
        s.query(NortPoleAuditEvent).filter(NortPoleAuditEvent.actor_email == ADMIN.email, NortPoleAuditEvent.row_hash.is_(None)).delete()
        s.query(NortPoleAuditEvent).filter(NortPoleAuditEvent.actor_email == f"old-{TAG}", NortPoleAuditEvent.row_hash.is_(None)).delete()
        s.query(NortPoleRouteUsage).filter(NortPoleRouteUsage.model_name == TAG).delete()
        s.query(NortPoleRedactionCount).filter(NortPoleRedactionCount.data_kind == "TEST").delete()
        s.commit()


def _seed(s):  # type: ignore[no-untyped-def]
    old, new = NOW - datetime.timedelta(days=60), NOW - datetime.timedelta(days=2)
    s.add_all([
        NortPoleAuditEvent(action="test.old", outcome="success", actor_email=f"old-{TAG}", summary="old", created_at=old),
        NortPoleAuditEvent(action="test.new", outcome="success", actor_email=f"old-{TAG}", summary="new", created_at=new),
        NortPoleRouteUsage(day=old.date(), route_kind="local", provider_id=1, model_name=TAG, data_class="public", purpose="chat", requests=1),
        NortPoleRouteUsage(day=new.date(), route_kind="local", provider_id=1, model_name=TAG, data_class="public", purpose="task_draft", requests=1),
        NortPoleRedactionCount(day=old.date(), route_kind="cloud", data_kind="TEST", items=1),
    ])
    s.commit()


def _counts(s):  # type: ignore[no-untyped-def]
    return (
        s.query(NortPoleAuditEvent).filter_by(actor_email=f"old-{TAG}").count(),
        s.query(NortPoleRouteUsage).filter_by(model_name=TAG).count(),
        s.query(NortPoleRedactionCount).filter_by(data_kind="TEST").count(),
    )


def test_prune_removes_only_what_is_older_than_the_period_and_records_itself() -> None:
    with get_session_with_current_tenant() as s:
        _seed(s)
        out = prune(s, now=NOW, actor=ADMIN, settings=Retention(audit_days=30, usage_days=30))
        assert out["held"] is False and out["audit_events"] >= 1 and out["usage_rows"] >= 1 and out["redaction_rows"] >= 1
        assert _counts(s) == (1, 1, 0), "the 2-day-old rows stay, the 60-day-old rows go"
        last = s.execute(text("select summary from nortpole_audit_event where action='retention.prune' and actor_email=:e order by id desc limit 1"), {"e": ADMIN.email}).scalar()
        assert last and last.startswith("Pruned ")


def test_a_legal_hold_stops_all_pruning() -> None:
    with get_session_with_current_tenant() as s:
        _seed(s)
        out = prune(s, now=NOW, actor=ADMIN, settings=Retention(audit_days=30, usage_days=30, legal_hold=True, hold_reason="case 12"))
        assert out["held"] is True and _counts(s) == (2, 2, 1)


def test_keeping_forever_prunes_nothing_of_that_kind() -> None:
    with get_session_with_current_tenant() as s:
        _seed(s)
        prune(s, now=NOW, actor=ADMIN, settings=Retention(audit_days=None, usage_days=30))
        assert _counts(s) == (2, 1, 0)


def test_periods_have_a_floor_and_a_hold_needs_a_reason() -> None:
    with pytest.raises(ValueError):
        Retention(audit_days=1)
    with pytest.raises(ValueError):
        ret_api.RetentionUpdate(audit_days=5)
    with pytest.raises(NortPoleError) as err:
        ret_api.put_retention(ret_api.RetentionUpdate(legal_hold=True, hold_reason="  "), user=ADMIN)
    assert "reason" in err.value.detail


def test_changing_retention_and_the_hold_is_audited_and_remembered() -> None:
    v = ret_api.put_retention(ret_api.RetentionUpdate(audit_days=400, usage_days=200, legal_hold=True, hold_reason="audit 2026"), user=ADMIN)
    assert (v.audit_days, v.usage_days, v.legal_hold, v.hold_set_by) == (400, 200, True, ADMIN.email)
    assert ret_api.get_retention(None).legal_hold is True
    v = ret_api.put_retention(ret_api.RetentionUpdate(audit_days=400, usage_days=200), user=ADMIN)
    assert v.legal_hold is False and v.hold_reason == ""
    with get_session_with_current_tenant() as s:
        rows = [r[0] for r in s.execute(text("select summary from nortpole_audit_event where action='retention.change' and actor_email=:e order by id"), {"e": ADMIN.email})]
    assert "legal hold placed: audit 2026" in rows[0] and rows[1].endswith("legal hold lifted")


def test_export_is_ordered_complete_audited_and_neutralises_spreadsheet_formulas() -> None:
    with get_session_with_current_tenant() as s:
        s.add_all([
            NortPoleAuditEvent(action="test.export", outcome="success", actor_email=f"old-{TAG}", summary="=HYPERLINK(\"http://evil\")", created_at=NOW),
            NortPoleAuditEvent(action="test.export", outcome="denied", actor_email=f"old-{TAG}", summary="plain, with comma", details={"k": "v"}, created_at=NOW),
        ])
        s.commit()
        j = json.loads(audit_api.export_events(format="json", since_id=0, until_id=None, user=ADMIN, db_session=s).body)
        mine = [r for r in j if r["actor_email"] == f"old-{TAG}"]
        assert [r["summary"] for r in mine][:2] == ['=HYPERLINK("http://evil")', "plain, with comma"]
        assert [r["id"] for r in j] == sorted(r["id"] for r in j)
        c = audit_api.export_events(format="csv", since_id=0, until_id=None, user=ADMIN, db_session=s)
        rows = [r for r in csv.reader(io.StringIO(c.body.decode())) if r and r[3] and f"old-{TAG}" in r]
        assert rows[0][7].startswith("'="), "a formula is shown as text"
        assert rows[1][7] == "plain, with comma" and rows[1][8] == '{"k": "v"}'
        logged = s.execute(text("select summary, details from nortpole_audit_event where action='audit.export' and actor_email=:e order by id desc limit 1"), {"e": ADMIN.email}).one()
        assert logged.summary.startswith("Exported ") and "rows" in logged.details
        assert "HYPERLINK" not in json.dumps(logged.details), "the export record holds counts, not content"
