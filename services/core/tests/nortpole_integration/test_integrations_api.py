"""The integration routes on the real database: the catalog a person sees, install, connect and remove, the
administrator's policy page, and what is logged (decision 0008, phase 2b-2). Handlers are called directly, as the other
NortPole route tests do; the HTTP gates are checked in test_endpoint_security."""

import json
import uuid
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.audit import NortPoleAuditEvent
from nortpole.knowledge.source_requests import api as requests_api
from nortpole.knowledge.source_requests.models import NortPoleSourceRequest
from nortpole.work.integrations import api, oauth, policy, registry, secrets
from nortpole.work.integrations.models import NortPoleIntegrationUse
from tests.nortpole_integration.test_tasks_flow import _up
from tests.unit.nortpole.integrations.test_manifest import GOOD

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]
SECRET = f"tok-SECRET-{TAG}"


@pytest.fixture()
def world(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv(secrets.ENV, secrets.generate_key())
    registry.reload()
    saved = policy.load()
    policy.save(policy.PolicyConfig())
    with get_session_with_current_tenant() as s:
        ann = User(id=uuid.uuid4(), email=f"api-ann-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        admin = User(id=uuid.uuid4(), email=f"api-admin-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add_all([ann, admin])
        s.commit()
        ids = {"ann": ann.id, "admin": admin.id}
    yield ids
    policy.save(saved)
    registry.reload()
    with get_session_with_current_tenant() as s:
        for uid in ids.values():
            s.query(NortPoleIntegrationUse).filter_by(user_id=uid).delete()
            s.query(NortPoleSourceRequest).filter_by(requested_by_id=uid).delete()
            s.query(User).filter_by(id=uid).delete()
        s.commit()


def code_of(fn, *a, **k):  # type: ignore[no-untyped-def]
    with pytest.raises(NortPoleError) as err:
        fn(*a, **k)
    return err.value.error_code if hasattr(err.value, "error_code") else err.value.code


def test_the_catalog_lists_everything_grouped_and_filterable_with_the_persons_own_state(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        everything = api.catalog(group=None, category=None, kind=None, q=None, user=ann, db=s)
        by_id = {i.id: i for i in everything.items}
        assert {"wikipedia", "airtable"} <= set(by_id)
        assert by_id["wikipedia"].state == "available" and by_id["airtable"].state == "needs_approval"
        assert by_id["airtable"].needs_account and not by_id["wikipedia"].needs_account
        assert by_id["airtable"].hosts == ["api.airtable.com"] and by_id["airtable"].has_writes
        keys = [(i.group, i.category, i.name.lower()) for i in everything.items]
        assert keys == sorted(keys), "Horizontal first, then Vertical, then category, then name"
        assert [i.id for i in api.catalog(group="vertical", category=None, kind=None, q=None, user=ann, db=s).items] == []
        assert [i.id for i in api.catalog(group="horizontal", category="automations", kind=None, q=None, user=ann, db=s).items] == ["airtable"]
        assert [i.id for i in api.catalog(group=None, category=None, kind="plugin", q="summary", user=ann, db=s).items] == ["wikipedia"]
        assert "credential" not in everything.model_dump_json().lower()


def test_install_connect_disconnect_and_remove_through_the_routes(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        assert api.install("wikipedia", api.IntegrationInstallBody(settings={"limit": 5}), user=ann, db=s).state == "installed"
        # refused flows carry the right code
        assert code_of(api.install, "wikipedia", api.IntegrationInstallBody(settings={"limit": 99}), user=ann, db=s) == NortPoleErrorCode.INVALID_INPUT
        assert code_of(api.install, "airtable", api.IntegrationInstallBody(), user=ann, db=s) == NortPoleErrorCode.POLICY_BLOCKED
        assert code_of(api.install, "nope", api.IntegrationInstallBody(), user=ann, db=s) == NortPoleErrorCode.NOT_FOUND
        assert code_of(api.connect, "airtable", api.IntegrationAccountBody(access_token=SECRET), user=ann, db=s) == NortPoleErrorCode.CONFLICT
        assert code_of(api.connect, "wikipedia", api.IntegrationAccountBody(access_token=SECRET), user=ann, db=s) == NortPoleErrorCode.INVALID_INPUT
        s.add(NortPoleSourceRequest(kind="plugin", item_key="integration:airtable", item_name="Airtable", reason="", state="approved", requested_by_id=ann.id, requested_by_email=ann.email))
        s.commit()
        assert api.install("airtable", api.IntegrationInstallBody(), user=ann, db=s).state == "installed"
        view = api.connect("airtable", api.IntegrationAccountBody(access_token=SECRET), user=ann, db=s)
        assert view.state == "connected" and SECRET not in view.model_dump_json()
        assert SECRET not in repr(api.IntegrationAccountBody(access_token=SECRET)), "a request body never shows the token in a log line"
        assert api.disconnect("airtable", user=ann, db=s).state == "installed"
        assert api.remove("airtable", user=ann, db=s).state == "available"


def test_a_missing_sealing_key_is_a_clear_refusal_and_stores_nothing(world, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import nortpole.utils.encryption as encryption

    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        policy.save(policy.PolicyConfig(integrations={"airtable": "allowed"}))
        api.install("airtable", api.IntegrationInstallBody(), user=ann, db=s)
        monkeypatch.delenv(secrets.ENV)
        monkeypatch.delenv("NORTPOLE_ALLOW_PLAINTEXT_SECRETS", raising=False)
        monkeypatch.setattr(encryption, "ENCRYPTION_KEY_SECRET", "")
        assert code_of(api.connect, "airtable", api.IntegrationAccountBody(access_token=SECRET), user=ann, db=s) == NortPoleErrorCode.FEATURE_DISABLED


def _write_capable_definition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = json.loads(json.dumps(GOOD))
    data.update(id="example-writer", policy_default="needs_approval")
    action = data["actions"][0]
    action.update(effect="write")
    action["request"].update(method="POST", body={"title": "{folder}"})
    folder = tmp_path / "horizontal/product/example-writer"
    folder.mkdir(parents=True)
    (folder / "integration.yaml").write_text(yaml.safe_dump(data))
    monkeypatch.setenv("NORTPOLE_INTEGRATIONS_DIR", str(tmp_path))
    registry.reload()


def test_the_policy_page_shows_every_item_with_counts_and_changes_are_audited(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann, admin = s.get(User, world["ann"]), s.get(User, world["admin"])
        api.install("wikipedia", api.IntegrationInstallBody(), user=ann, db=s)
        view = api.get_policy(_=admin, db=s)
        rows = {r.id: r for r in view.items}
        assert rows["wikipedia"].installs >= 1 and rows["wikipedia"].effective == "allowed" and rows["airtable"].effective == "needs_approval"
        assert rows["airtable"].default == "needs_approval" and rows["airtable"].override is None
        assert code_of(api.put_policy, api.IntegrationPolicyBody(config=policy.PolicyConfig(integrations={"ghost": "blocked"})), user=admin, db=s) == NortPoleErrorCode.INVALID_INPUT
        changed = api.put_policy(api.IntegrationPolicyBody(config=policy.PolicyConfig(integrations={"wikipedia": "blocked"}, categories={"horizontal/automations": "allowed"}), acknowledge_writes=True), user=admin, db=s)
        rows = {r.id: r for r in changed.items}
        assert rows["wikipedia"].effective == "blocked" and rows["airtable"].effective == "allowed" and rows["airtable"].category_override == "allowed"
    with get_session_with_current_tenant() as s:
        event = s.scalars(
            select(NortPoleAuditEvent).where(
                NortPoleAuditEvent.action == "integration.policy_change",
                NortPoleAuditEvent.actor_user_id == str(world["admin"]),
            )
        ).one()
        assert event.details is not None
        assert event.details["integrations"]["wikipedia"] == [None, "blocked"]


def test_letting_people_use_a_write_action_without_asking_needs_a_confirmation(world, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _write_capable_definition(tmp_path, monkeypatch)
    with get_session_with_current_tenant() as s:
        admin = s.get(User, world["admin"])
        open_it = policy.PolicyConfig(integrations={"example-writer": "allowed"})
        assert code_of(api.put_policy, api.IntegrationPolicyBody(config=open_it), user=admin, db=s) == NortPoleErrorCode.INVALID_INPUT
        assert policy.load().integrations == {}, "nothing was saved without the confirmation"
        done = api.put_policy(api.IntegrationPolicyBody(config=open_it, acknowledge_writes=True), user=admin, db=s)
        assert {r.id: r for r in done.items}["example-writer"].has_writes
    with get_session_with_current_tenant() as s:
        event = s.scalars(
            select(NortPoleAuditEvent).where(
                NortPoleAuditEvent.action == "integration.policy_change",
                NortPoleAuditEvent.actor_user_id == str(world["admin"]),
            )
        ).one()
        assert event.details is not None
        assert event.details["opens_writes"] == ["example-writer"]
        # tightening again needs no confirmation
        api.put_policy(api.IntegrationPolicyBody(config=policy.PolicyConfig()), user=s.get(User, world["admin"]), db=s)


def test_an_integration_that_needs_approval_is_requested_approved_and_then_installable(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann, admin = s.get(User, world["ann"]), s.get(User, world["admin"])
        ask = requests_api.NewRequest(kind="plugin", item_key="integration:airtable", reason="for the ops report")
        # an allowed integration has nothing to request, and an unknown one is not found
        assert code_of(requests_api.create_request, requests_api.NewRequest(kind="plugin", item_key="integration:wikipedia"), user=ann, db_session=s) == NortPoleErrorCode.NOT_FOUND
        assert code_of(requests_api.create_request, requests_api.NewRequest(kind="plugin", item_key="integration:ghost"), user=ann, db_session=s) == NortPoleErrorCode.NOT_FOUND
        assert code_of(requests_api.create_request, requests_api.NewRequest(kind="skill", item_key="integration:airtable"), user=ann, db_session=s) == NortPoleErrorCode.NOT_FOUND
        sent = requests_api.create_request(ask, user=ann, db_session=s)
        assert sent.state == "pending" and sent.manage_at == "/admin/integrations", "the administrator is sent to the Integrations page"
        assert code_of(requests_api.create_request, ask, user=ann, db_session=s) == NortPoleErrorCode.CONFLICT, "one waiting request per item"
        assert code_of(api.install, "airtable", api.IntegrationInstallBody(), user=ann, db=s) == NortPoleErrorCode.POLICY_BLOCKED, "asking does not turn anything on"
        done = requests_api.decide_request(sent.id, requests_api.Decision(approve=True, note="ok"), user=admin, db_session=s)
        assert done.state == "approved"
        assert api.detail("airtable", user=ann, db=s).state == "available"
        assert api.install("airtable", api.IntegrationInstallBody(), user=ann, db=s).state == "installed"
        # a blocked integration cannot be requested
        policy.save(policy.PolicyConfig(integrations={"airtable": "blocked"}))
        assert code_of(requests_api.create_request, requests_api.NewRequest(kind="plugin", item_key="integration:airtable"), user=admin, db_session=s) == NortPoleErrorCode.NOT_FOUND


def test_two_integrations_never_share_a_schema_name_with_another_route_module() -> None:
    """A schema name used by two route modules silently replaces one with the other in the generated API description."""
    import importlib
    import inspect

    from pydantic import BaseModel

    import nortpole.main as main

    seen: dict[str, set[str]] = {}
    for route in main.get_application().routes:
        endpoint = getattr(route, "endpoint", None)
        module = getattr(endpoint, "__module__", "") or ""
        if not module.startswith("nortpole.work.integrations"):
            continue
        for name, obj in vars(importlib.import_module(module)).items():
            if inspect.isclass(obj) and issubclass(obj, BaseModel) and obj.__module__ == module:
                seen.setdefault(obj.__name__, set()).add(module)
    clashes = []
    for name in seen:
        for route in main.get_application().routes:
            endpoint = getattr(route, "endpoint", None)
            module = getattr(endpoint, "__module__", "") or ""
            if module.startswith("nortpole.work.integrations") or not module.startswith("nortpole"):
                continue
            if inspect.isclass(vars(importlib.import_module(module)).get(name)):
                clashes.append((name, module))
    assert not clashes, f"rename these: {sorted(set(clashes))}"


def test_sign_in_with_oauth_through_the_routes_connects_the_account_and_redirects_without_secrets(world, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from urllib.parse import parse_qs, urlsplit

    import httpx

    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        s.add(NortPoleSourceRequest(kind="plugin", item_key="integration:airtable", item_name="Airtable", reason="", state="approved", requested_by_id=ann.id, requested_by_email=ann.email))
        s.commit()
        # Nobody set the client up: the button is not offered and starting says why.
        assert not api.detail("airtable", user=ann, db=s).oauth_available
        assert code_of(api.oauth_start, "airtable", user=ann, db=s) == NortPoleErrorCode.CONFLICT, "install first"
        api.install("airtable", api.IntegrationInstallBody(), user=ann, db=s)
        assert code_of(api.oauth_start, "airtable", user=ann, db=s) == NortPoleErrorCode.FEATURE_DISABLED
        assert code_of(api.oauth_start, "wikipedia", user=ann, db=s) == NortPoleErrorCode.INVALID_INPUT, "no sign-in to do"
        assert code_of(api.oauth_start, "nope", user=ann, db=s) == NortPoleErrorCode.NOT_FOUND

        monkeypatch.setenv("NORTPOLE_OAUTH_AIRTABLE_CLIENT_ID", "cid")
        monkeypatch.setenv("NORTPOLE_OAUTH_AIRTABLE_CLIENT_SECRET", "csecret")
        monkeypatch.setattr(oauth, "token_validate", lambda url: url)
        monkeypatch.setattr(oauth, "token_transport", httpx.MockTransport(lambda r: httpx.Response(200, json={"access_token": f"AT-{SECRET}", "refresh_token": f"RT-{SECRET}", "expires_in": 3600}, headers={"content-type": "application/json"})))
        assert api.detail("airtable", user=ann, db=s).oauth_available
        url = api.oauth_start("airtable", user=ann, db=s).authorize_url
        state = parse_qs(urlsplit(url).query)["state"][0]
        assert str(ann.id) not in url

        # The page the service sent the person back to hands over the code; the account is connected and nothing leaks.
        done = api.oauth_complete(api.IntegrationOAuthComplete(state=state, code="the-code"), user=ann, db=s)
        assert done.state == "connected" and SECRET not in done.model_dump_json()
        raw = s.execute(__import__("sqlalchemy").text("select credential from nortpole_integration_use where user_id = :u and integration_id = 'airtable'"), {"u": ann.id}).scalar()
        assert raw and SECRET not in raw, "stored sealed"
        assert "the-code" not in repr(api.IntegrationOAuthComplete(state=state, code="the-code")), "a code never shows in a log line"

        # Refusals: a link someone else started, a link that is not one, and a refusal from the service.
        bob = s.get(User, world["admin"])
        assert code_of(api.oauth_complete, api.IntegrationOAuthComplete(state=state, code="c"), user=bob, db=s) == NortPoleErrorCode.BAD_REQUEST
        assert code_of(api.oauth_complete, api.IntegrationOAuthComplete(state="not-a-state", code="c"), user=ann, db=s) == NortPoleErrorCode.BAD_REQUEST
        monkeypatch.setattr(oauth, "token_transport", httpx.MockTransport(lambda r: httpx.Response(400, json={"error": "invalid_grant"})))
        assert code_of(api.oauth_complete, api.IntegrationOAuthComplete(state=state, code="c"), user=ann, db=s) == NortPoleErrorCode.BAD_REQUEST
        assert api.detail("airtable", user=ann, db=s).state == "connected", "a failed attempt leaves the account as it was"
