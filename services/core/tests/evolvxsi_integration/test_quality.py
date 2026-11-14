"""The admin quality summary counts runs, evaluations, feedback and daily trends, and never returns anyone's text."""

import datetime
import json
import uuid

import pytest

from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.models import User
from evolvxsi.work.packs.models import EvolvXSIPackEvaluation
from evolvxsi.insight.quality.api import MAX_DAYS, build
from evolvxsi.work.tasks.models import EvolvXSITask
from tests.evolvxsi_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]
PACK = f"quality-test-{TAG}"


def _task(owner, now, *, state, drafted=False, approved=False, claims=None, secs=40):
    started = now - datetime.timedelta(hours=1)
    return EvolvXSITask(
        owner_id=owner.id, title=f"Secret title {TAG}", request=f"secret request {TAG}", state=state, version=1,
        pack_id=PACK, started_at=started, drafted_at=started + datetime.timedelta(seconds=secs) if drafted else None,
        approved_at=now if approved else None, draft_claims=claims,
        draft_text=f"secret draft {TAG}" if drafted else None,
    )


def test_runs_evals_and_trends_are_counted_without_text() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    claims = [
        {"i": 0, "text": f"secret claim {TAG}", "cites": [1], "status": "supported", "decision": None},
        {"i": 1, "text": f"secret claim two {TAG}", "cites": [], "status": "unsupported", "decision": "remove"},
        {"i": 2, "text": f"secret claim three {TAG}", "cites": [], "status": "unsupported", "decision": None},
    ]
    with get_session_with_current_tenant() as s:
        owner = s.query(User).first()
        rows = [
            _task(owner, now, state="approved", drafted=True, approved=True, claims=claims, secs=30),
            _task(owner, now, state="draft_ready", drafted=True, secs=50),
            _task(owner, now, state="run_failed"),
        ]
        ev = EvolvXSIPackEvaluation(
            pack_id=PACK, version="1.0.0", model_configuration_id=987654, model_name="quality-model", route_kind="local",
            passed=False, cases_total=2, cases_passed=1,
            details=[{"question": f"Q ok {TAG}", "passed": True, "reason": ""}, {"question": f"Q bad {TAG}", "passed": False, "reason": f"secret reason {TAG}"}],
        )
        s.add_all(rows + [ev]); s.commit()
        try:
            out = build(s, 30, now + datetime.timedelta(seconds=1))
            mine = next(r for r in out["runs"]["by_pack"] if r["pack_id"] == PACK)
            assert (mine["started"], mine["drafted"], mine["failed"], mine["approved"]) == (3, 2, 1, 1)
            assert out["runs"]["median_seconds_to_draft"] is not None
            assert out["runs"]["claims"]["unsupported"] >= 2 and out["runs"]["claims"]["removed"] >= 1 and out["runs"]["claims"]["undecided"] >= 1
            e = next(x for x in out["evals"] if x["pack_id"] == PACK)
            assert (e["passed"], e["cases_passed"], e["cases_total"], e["route_kind"]) == (False, 1, 2, "local")
            assert e["failed_questions"] == [f"Q bad {TAG}"]
            today = out["trends"][-1]
            assert today["date"] == now.date().isoformat() and today["started"] >= 3 and today["failed"] >= 1 and today["approved"] >= 1
            assert len(out["trends"]) == 30 and out["window_days"] == 30
            text = json.dumps(out)
            for secret in (f"Secret title {TAG}", f"secret request {TAG}", f"secret draft {TAG}", f"secret claim {TAG}", f"secret reason {TAG}"):
                assert secret not in text, f"{secret!r} must not reach the quality summary"
        finally:
            for r in rows:
                s.delete(s.get(EvolvXSITask, r.id))
            s.delete(s.get(EvolvXSIPackEvaluation, ev.row_id)); s.commit()


def test_window_is_clamped_and_empty_windows_have_no_rates() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    with get_session_with_current_tenant() as s:
        assert build(s, 9999, now)["window_days"] == MAX_DAYS and len(build(s, 9999, now)["trends"]) == MAX_DAYS
        assert build(s, 0, now)["window_days"] == 1
        far = build(s, 1, now + datetime.timedelta(days=400))
        assert far["runs"]["totals"]["started"] == 0 and far["runs"]["draft_rate"] is None and far["runs"]["median_seconds_to_draft"] is None
