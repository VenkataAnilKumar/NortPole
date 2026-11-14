"""Allowed model requests are counted by route, without people or text."""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.governance.route_policy import api as route_api
from evolvxsi.governance.route_policy.usage import EvolvXSIRouteUsage, record_usage
from tests.evolvxsi_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the usage table")

MODEL = f"usage-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _clean():  # type: ignore[no-untyped-def]
    yield
    with get_session_with_current_tenant() as s:
        s.query(EvolvXSIRouteUsage).filter_by(model_name=MODEL).delete()
        s.commit()


def test_requests_are_counted_per_route_model_class_and_purpose() -> None:
    for _ in range(3):
        record_usage(route_kind="local", provider_id=1, model_name=MODEL, data_class="confidential", purpose="task_draft")
    record_usage(route_kind="local", provider_id=1, model_name=MODEL, data_class="confidential", purpose="task_plan")
    record_usage(route_kind="cloud", provider_id=2, model_name=MODEL, data_class="public", purpose="chat")
    with get_session_with_current_tenant() as s:
        rows = {(r.route_kind, r.data_class, r.purpose): r.requests for r in route_api.get_route_usage(days=1, _=None, db_session=s) if r.model_name == MODEL}
    assert rows == {("local", "confidential", "task_draft"): 3, ("local", "confidential", "task_plan"): 1, ("cloud", "public", "chat"): 1}


def test_the_table_holds_no_person_or_text_column() -> None:
    with get_session_with_current_tenant() as s:
        cols = {r[0] for r in s.execute(text("select column_name from information_schema.columns where table_name='evolvxsi_route_usage'"))}
    assert cols == {"row_id", "day", "route_kind", "provider_id", "model_name", "data_class", "purpose", "requests"}


def test_a_failure_to_count_never_stops_the_request(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from evolvxsi.governance.route_policy import usage

    monkeypatch.setattr(usage, "get_session_with_current_tenant", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    record_usage(route_kind="local", provider_id=1, model_name=MODEL, data_class="public", purpose="chat")  # must not raise


def test_enforce_route_counts_only_allowed_requests_that_name_a_purpose() -> None:
    from unittest.mock import patch

    from evolvxsi.error_handling.exceptions import EvolvXSIError
    from evolvxsi.governance.route_policy import enforce

    allowed = SimpleNamespace(allowed=True, kind="local", data_class="internal", reason=None)
    blocked = SimpleNamespace(allowed=False, kind="cloud", data_class="restricted", reason="no")
    calls: list[dict] = []
    row = SimpleNamespace(llm_provider_id=7, name=MODEL)
    db = SimpleNamespace(get=lambda *_: row)
    with patch.object(enforce, "check_route", return_value=allowed), patch("evolvxsi.governance.route_policy.usage.record_usage", lambda **k: calls.append(k)):
        enforce.enforce_route(db, 5)
        assert calls == []
        enforce.enforce_route(db, 5, purpose="chat")
        assert calls == [{"route_kind": "local", "provider_id": 7, "model_name": MODEL, "data_class": "internal", "purpose": "chat"}]
    calls.clear()
    with patch.object(enforce, "check_route", return_value=blocked), patch("evolvxsi.governance.route_policy.usage.record_usage", lambda **k: calls.append(k)), \
         patch.object(enforce, "record_audit"):
        with pytest.raises(EvolvXSIError):
            enforce.enforce_route(db, 5, purpose="chat")
    assert calls == []
