"""Tokens and an estimated cost are counted by route and model, without people or text; an unknown price is not shown as free."""

import datetime
import uuid

import pytest
from sqlalchemy import text

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.governance.route_policy import api as route_api
from nortpole.governance.route_policy.usage import NortPoleRouteTokens, is_priced, record_tokens
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the tokens table")

TAG = uuid.uuid4().hex[:8]
UNPRICED = f"tokens-unpriced-{TAG}"
LOCAL = f"tokens-local-{TAG}"


@pytest.fixture(autouse=True)
def _clean():  # type: ignore[no-untyped-def]
    yield
    with get_session_with_current_tenant() as s:
        s.query(NortPoleRouteTokens).filter(NortPoleRouteTokens.model_name.in_([UNPRICED, LOCAL])).delete(synchronize_session=False)
        s.commit()


def _rows(model: str):  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        return [r for r in route_api.get_route_tokens(days=1, _=None, db_session=s) if r.model_name == model]


def test_tokens_add_up_and_an_unknown_price_is_not_called_free() -> None:
    for _ in range(2):
        record_tokens(model_configuration_id=None, model_version=UNPRICED, provider="openai", served_model=None,
                      prompt_tokens=100, completion_tokens=50)
    (row,) = _rows(UNPRICED)
    assert (row.calls, row.prompt_tokens, row.completion_tokens, row.unpriced_calls) == (2, 200, 100, 2)
    assert row.route_kind == "unknown"
    assert row.estimated_cost_cents is None, "no call had a known price, so no cost figure is claimed"


def test_a_model_on_this_deployments_own_hardware_is_priced_at_zero() -> None:
    record_tokens(model_configuration_id=None, model_version=LOCAL, provider="ollama_chat", served_model=None,
                  prompt_tokens=10, completion_tokens=5)
    (row,) = _rows(LOCAL)
    assert row.unpriced_calls == 0 and row.estimated_cost_cents == 0.0 and row.prompt_tokens == 10


def test_negative_token_counts_are_not_stored() -> None:
    record_tokens(model_configuration_id=None, model_version=UNPRICED, provider="openai", served_model=None,
                  prompt_tokens=-5, completion_tokens=-1)
    (row,) = _rows(UNPRICED)
    assert row.prompt_tokens == 0 and row.completion_tokens == 0 and row.calls == 1


def test_the_table_holds_no_person_or_text_column() -> None:
    with get_session_with_current_tenant() as s:
        cols = {r[0] for r in s.execute(text("select column_name from information_schema.columns where table_name='evolvxsi_route_tokens'"))}
    assert cols == {"row_id", "day", "route_kind", "provider_id", "model_name", "calls", "prompt_tokens", "completion_tokens",
                    "cost_cents", "unpriced_calls"}


def test_a_failure_to_count_never_stops_the_request(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from nortpole.governance.route_policy import usage

    monkeypatch.setattr(usage, "get_session_with_current_tenant", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    record_tokens(model_configuration_id=None, model_version=UNPRICED, provider="openai", served_model=None,
                  prompt_tokens=1, completion_tokens=1)  # must not raise


def test_retention_prunes_old_token_rows_with_the_usage_rows() -> None:
    from nortpole.governance.retention.prune import prune
    from nortpole.governance.retention.settings import Retention

    now = datetime.datetime.now(datetime.timezone.utc)
    old = (now - datetime.timedelta(days=100)).date()
    with get_session_with_current_tenant() as s:
        s.add(NortPoleRouteTokens(day=old, route_kind="local", provider_id=-1, model_name=LOCAL, calls=1, prompt_tokens=1,
                                  completion_tokens=1, cost_cents=0, unpriced_calls=0))
        s.commit()
        out = prune(s, now=now, actor=None, settings=Retention(audit_days=None, usage_days=30))
        assert out["usage_rows"] >= 1
        assert s.query(NortPoleRouteTokens).filter_by(model_name=LOCAL, day=old).count() == 0


def test_which_calls_count_as_priced() -> None:
    assert is_priced(0.4, "cloud", False), "a cost from the price list is known"
    assert is_priced(0.0, "local", False), "a route marked local costs nothing per token"
    assert is_priced(0.0, "unknown", True), "a provider on this deployment's own hardware costs nothing per token"
    assert not is_priced(0.0, "cloud", False), "no price-list entry on a cloud route is not free"
    assert not is_priced(0.0, "private", False), "a private route's price is not known to this product"
    assert not is_priced(0.0, "unknown", False)
