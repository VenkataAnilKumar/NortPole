"""Running an integration action: the request it builds, what it refuses, and the log it leaves (decision 0008)."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from nortpole.work.integrations import executor
from nortpole.work.integrations.executor import IntegrationCallError, PreparedRequest, extract, prepare, read_path, run
from nortpole.work.integrations.manifest import Integration

ROOT = Path(__file__).resolve().parents[6] / "integrations"


def load(path: str) -> Integration:
    return Integration.model_validate(yaml.safe_load((ROOT / path / "integration.yaml").read_text(encoding="utf-8")))


WIKI = load("horizontal/product/wikipedia")
AIR = load("horizontal/automations/airtable")
TOKEN = {"access_token": "tok-SECRET-123"}


def test_wikipedia_search_builds_the_documented_request() -> None:
    req = prepare(WIKI, "search", model_params={"query": "north pole"})
    assert req.method == "GET" and req.host == "en.wikipedia.org"
    assert req.url == "https://en.wikipedia.org/w/api.php"
    assert req.query == {"action": "query", "list": "search", "format": "json", "srsearch": "north pole", "srlimit": "10"}
    assert req.headers["User-Agent"] == "NortPole/1.0"


def test_a_parameter_only_the_person_may_set_is_refused_from_the_model() -> None:
    with pytest.raises(IntegrationCallError, match="can't be set by the model"):
        prepare(WIKI, "search", model_params={"query": "x", "limit": 50})
    req = prepare(WIKI, "search", user_params={"limit": 25}, model_params={"query": "x"})
    assert req.query["srlimit"] == "25"


def test_path_values_are_url_encoded() -> None:
    req = prepare(WIKI, "page_summary", model_params={"pageTitle": "AC/DC & Co?"})
    assert req.url == "https://en.wikipedia.org/api/rest_v1/page/summary/AC%2FDC%20%26%20Co%3F"


def test_optional_values_that_are_absent_are_left_out_and_the_credential_goes_in_a_header() -> None:
    req = prepare(AIR, "list_records", model_params={"baseId": "appX", "tableId": "tblY"}, credential=TOKEN)
    assert req.url == "https://api.airtable.com/v0/appX/tblY"
    assert req.query == {}
    assert req.headers == {"Authorization": "Bearer tok-SECRET-123"}


def test_the_credential_never_shows_in_a_repr() -> None:
    req = prepare(AIR, "list_bases", credential=TOKEN)
    assert "SECRET" not in repr(req) and "SECRET" not in str(req)


def test_an_action_that_needs_an_account_refuses_without_one() -> None:
    with pytest.raises(IntegrationCallError) as err:
        prepare(AIR, "list_bases")
    assert err.value.code == "not_connected"
    with pytest.raises(IntegrationCallError):
        prepare(AIR, "list_bases", credential={"access_token": ""})


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"model_params": {}}, "missing_parameter"),
        ({"model_params": {"query": "x", "nope": 1}}, "bad_parameter"),
        ({"model_params": {"query": 5}}, "bad_parameter"),
        ({"model_params": {"query": "a\r\nHost: evil"}}, "bad_parameter"),
        ({"model_params": {"query": "x" * 501}}, "bad_parameter"),
        ({"user_params": {"limit": 0}, "model_params": {"query": "x"}}, "bad_parameter"),
        ({"user_params": {"limit": 51}, "model_params": {"query": "x"}}, "bad_parameter"),
        ({"user_params": {"limit": True}, "model_params": {"query": "x"}}, "bad_parameter"),
        ({"user_params": {"query": "x"}, "model_params": {"query": "y"}}, "bad_parameter"),
    ],
)
def test_bad_parameters_are_refused(kwargs: dict, code: str) -> None:
    with pytest.raises(IntegrationCallError) as err:
        prepare(WIKI, "search", **kwargs)
    assert err.value.code == code


def test_an_unknown_action_is_refused() -> None:
    with pytest.raises(IntegrationCallError, match="no action"):
        prepare(WIKI, "delete_everything")


def test_a_definition_built_in_code_still_cannot_reach_another_host() -> None:
    data = yaml.safe_load((ROOT / "horizontal/product/wikipedia/integration.yaml").read_text(encoding="utf-8"))
    data["actions"][0]["request"]["url"] = "https://evil.example.org/x/{pageTitle}"
    forged = Integration.model_construct(**{**data, "actions": [__import__("nortpole.work.integrations.manifest", fromlist=["Action"]).Action.model_validate(data["actions"][0])]})
    with pytest.raises(IntegrationCallError) as err:
        prepare(forged, "page_summary", model_params={"pageTitle": "x"})
    assert err.value.code == "host_not_allowed"


def test_reading_values_out_of_a_response() -> None:
    payload = {"records": [{"id": "r1", "fields": {"a": 1}}, {"id": "r2"}], "offset": "next", "query": {"search": [{"title": "T"}]}}
    assert read_path(payload, "$.offset") == "next"
    assert read_path(payload, "$.records[0].id") == "r1"
    assert read_path(payload, "$.records[*].id") == ["r1", "r2"]
    assert read_path(payload, "$.query.search[*]") == [{"title": "T"}]
    assert read_path(payload, "$.missing.deeper") is None
    assert read_path(payload, "$.records[9]") is None


def test_outputs_follow_the_declared_types() -> None:
    action = next(a for a in AIR.actions if a.id == "list_records")
    assert extract(action, {"records": [{"id": "r"}], "offset": "o"}) == {"records": [{"id": "r"}], "offset": "o"}
    assert extract(action, {"records": "not a list", "offset": 3}) == {"records": [], "offset": None}
    assert extract(action, {}) == {"records": [], "offset": None}


# ---- run -----------------------------------------------------------------------------------------------------------------


def fake(status: int = 200, body: Any = None, content_type: str = "application/json; charset=utf-8"):  # type: ignore[no-untyped-def]
    seen: list[PreparedRequest] = []

    def transport(request: PreparedRequest) -> tuple[int, bytes, str]:
        seen.append(request)
        return status, json.dumps(body if body is not None else {}).encode(), content_type

    transport.seen = seen  # type: ignore[attr-defined]
    return transport


@pytest.fixture()
def audit(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    rows: list[dict] = []
    import nortpole.governance.route_policy.audit as audit_module

    monkeypatch.setattr(audit_module, "record_audit", lambda *a, **k: rows.append({"args": a, **k}))
    return rows


def test_a_call_returns_the_named_outputs_and_is_logged_without_secrets(audit: list[dict]) -> None:
    transport = fake(body={"records": [{"id": "r1"}], "offset": None})
    out = run(AIR, "list_records", model_params={"baseId": "appSECRETBASE", "tableId": "tbl"}, credential=TOKEN, user_id="u1", transport=transport)
    assert out == {"records": [{"id": "r1"}], "offset": None}
    assert len(audit) == 1
    row = audit[0]
    assert row["details"]["outcome"] == "returned" and row["details"]["host"] == "api.airtable.com" and row["details"]["user_id"] == "u1"
    assert "SECRET" not in json.dumps(row, default=str), "neither the token nor a parameter value may be logged"


@pytest.mark.parametrize(
    "status, body, ctype, code",
    [
        (500, {"error": "leaks a customer name"}, "application/json", "service_error"),
        (404, {}, "application/json", "service_error"),
        (302, {}, "application/json", "redirect"),
        (200, {}, "text/html", "not_json"),
    ],
)
def test_failures_are_reported_without_the_response_body(audit: list[dict], status: int, body: dict, ctype: str, code: str) -> None:
    with pytest.raises(IntegrationCallError) as err:
        run(WIKI, "search", model_params={"query": "x"}, transport=fake(status, body, ctype))
    assert err.value.code == code
    assert "customer" not in str(err.value)
    assert audit[-1]["details"]["outcome"] in ("service_error", "refused")


def test_a_refused_call_is_logged_and_nothing_is_sent(audit: list[dict]) -> None:
    transport = fake()
    with pytest.raises(IntegrationCallError):
        run(AIR, "list_bases", transport=transport)  # not connected
    assert not transport.seen  # type: ignore[attr-defined]
    assert audit[-1]["details"]["outcome"] == "refused"


def test_the_real_transport_sends_what_was_prepared_and_does_not_follow_redirects() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/redirect"):
            return httpx.Response(302, headers={"location": "https://evil.example.org/"})
        return httpx.Response(200, json={"records": [], "offset": None})

    req = prepare(AIR, "list_records", model_params={"baseId": "appX", "tableId": "tblY"}, user_params={}, credential=TOKEN)
    status, body, ctype = executor.http_transport(req, httpx_transport=httpx.MockTransport(handler), validate=lambda u: u)
    assert status == 200 and "json" in ctype
    assert seen[0].headers["authorization"] == "Bearer tok-SECRET-123"
    redirect = PreparedRequest("GET", "https://api.airtable.com/redirect", {}, None, {})
    status, _, _ = executor.http_transport(redirect, httpx_transport=httpx.MockTransport(handler), validate=lambda u: u)
    assert status == 302 and len(seen) == 2, "the redirect was returned, not followed"


def test_the_real_transport_stops_a_response_over_the_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(executor, "MAX_RESPONSE_BYTES", 100)
    handler = lambda request: httpx.Response(200, content=b"x" * 500, headers={"content-type": "application/json"})  # noqa: E731
    req = PreparedRequest("GET", "https://api.airtable.com/x", {}, None, {})
    with pytest.raises(IntegrationCallError) as err:
        executor.http_transport(req, httpx_transport=httpx.MockTransport(handler), validate=lambda u: u)
    assert err.value.code == "too_large"


def test_the_address_safety_check_runs_before_any_request() -> None:
    called: list[str] = []

    def validate(url: str) -> str:
        called.append(url)
        raise ValueError("blocked")

    req = PreparedRequest("GET", "https://api.airtable.com/x", {}, None, {})
    with pytest.raises(ValueError):
        executor.http_transport(req, httpx_transport=httpx.MockTransport(lambda r: httpx.Response(200)), validate=validate)
    assert called == ["https://api.airtable.com/x"]
