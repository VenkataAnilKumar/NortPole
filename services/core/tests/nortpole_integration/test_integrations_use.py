"""A person's use of integrations on the real database: installing under each policy, connecting their own account,
making a call as them, and what is stored and logged (decision 0008, phase 2b)."""

import json
import uuid

import pytest
from sqlalchemy import select, text

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.governance.route_policy.audit import NortPoleAuditEvent
from nortpole.knowledge.source_requests.models import NortPoleSourceRequest
from nortpole.work.integrations import policy, registry, secrets, service
from nortpole.work.integrations.models import NortPoleIntegrationUse
from nortpole.work.integrations.service import IntegrationAccessError
from tests.nortpole_integration.test_tasks_flow import _up

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
        ann = User(id=uuid.uuid4(), email=f"int-ann-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        bob = User(id=uuid.uuid4(), email=f"int-bob-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add_all([ann, bob])
        s.commit()
        ids = {"ann": ann.id, "bob": bob.id}
    yield ids
    policy.save(saved)
    with get_session_with_current_tenant() as s:
        for uid in ids.values():
            s.query(NortPoleIntegrationUse).filter_by(user_id=uid).delete()
            s.query(NortPoleSourceRequest).filter_by(requested_by_id=uid).delete()
            s.query(User).filter_by(id=uid).delete()
        s.commit()


def fake(body, status=200):  # type: ignore[no-untyped-def]
    seen = []

    def transport(request):  # type: ignore[no-untyped-def]
        seen.append(request)
        return status, json.dumps(body).encode(), "application/json"

    transport.seen = seen  # type: ignore[attr-defined]
    return transport


def person(s, ids, name):  # type: ignore[no-untyped-def]
    return s.get(User, ids[name])


def refused(code, fn, *a, **k):  # type: ignore[no-untyped-def]
    with pytest.raises(IntegrationAccessError) as err:
        fn(*a, **k)
    assert err.value.code == code
    return err.value


def audit_rows(action: str, contains: str):  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        return [r for r in s.scalars(select(NortPoleAuditEvent).where(NortPoleAuditEvent.action == action)).all()
                if contains in json.dumps(r.details or {}) + (r.actor_email or "")]


def test_an_allowed_integration_is_installed_and_called_without_an_approval(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = person(s, world, "ann")
        assert service.status(s, ann, "wikipedia")["state"] == "available"
        assert service.install(s, ann, "wikipedia", {"limit": 5})["state"] == "installed"
        transport = fake({"query": {"search": [{"title": "North Pole"}]}})
        out = service.call(s, ann, "wikipedia", "search", model_params={"query": "north pole"}, transport=transport)
        assert out == {"results": [{"title": "North Pole"}]}
        assert transport.seen[0].query["srlimit"] == "5", "the person's own setting was used"  # type: ignore[attr-defined]
        # an action without that setting still works: settings only go to actions that have the parameter
        out = service.call(s, ann, "wikipedia", "page_summary", model_params={"pageTitle": "North Pole"}, transport=fake({"title": "North Pole", "extract": "x"}))
        assert out["title"] == "North Pole"


def test_a_person_cannot_use_what_another_person_installed(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        service.install(s, person(s, world, "ann"), "wikipedia")
        refused("not_installed", service.call, s, person(s, world, "bob"), "wikipedia", "search", model_params={"query": "x"}, transport=fake({}))


def test_settings_are_checked(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = person(s, world, "ann")
        refused("bad_settings", service.install, s, ann, "wikipedia", {"limit": 99})
        refused("bad_settings", service.install, s, ann, "wikipedia", {"query": "the model's job, not a setting"})
        refused("bad_settings", service.install, s, ann, "wikipedia", {"nope": 1})


def test_an_integration_that_needs_approval_waits_for_one_then_connects_with_the_persons_own_account(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann, bob = person(s, world, "ann"), person(s, world, "bob")
        assert service.status(s, ann, "airtable")["state"] == "needs_approval"
        refused("needs_approval", service.install, s, ann, "airtable")
        s.add(NortPoleSourceRequest(kind="plugin", item_key="airtable", item_name="Airtable", reason="", state="approved", requested_by_id=ann.id, requested_by_email=ann.email))
        s.commit()
        assert service.status(s, ann, "airtable")["state"] == "available"
        assert service.status(s, bob, "airtable")["state"] == "needs_approval", "an approval is for one person"
        refused("needs_approval", service.install, s, bob, "airtable")
        assert service.install(s, ann, "airtable")["state"] == "installed"
        refused("not_connected", service.call, s, ann, "airtable", "list_bases", transport=fake({}))
        refused("bad_credential", service.connect, s, ann, "airtable", {"api_key": "wrong kind"})
        refused("bad_credential", service.connect, s, ann, "airtable", {"access_token": ""})
        assert service.connect(s, ann, "airtable", {"access_token": SECRET})["state"] == "connected"
        transport = fake({"bases": [{"id": "appA", "name": "Ops"}]})
        out = service.call(s, ann, "airtable", "list_bases", transport=transport)
        assert out["bases"] == [{"id": "appA", "name": "Ops"}]
        assert transport.seen[0].headers["Authorization"] == f"Bearer {SECRET}"  # type: ignore[attr-defined]
        assert SECRET not in repr(transport.seen[0])  # type: ignore[attr-defined]


def test_the_account_is_sealed_at_rest_and_never_in_status_or_logs(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = person(s, world, "ann")
        s.add(NortPoleSourceRequest(kind="plugin", item_key="airtable", item_name="Airtable", reason="", state="approved", requested_by_id=ann.id, requested_by_email=ann.email))
        s.commit()
        service.install(s, ann, "airtable")
        status = service.connect(s, ann, "airtable", {"access_token": SECRET, "refresh_token": f"ref-{SECRET}"})
        service.call(s, ann, "airtable", "list_bases", transport=fake({"bases": []}))
        assert SECRET not in json.dumps(status)
        raw = s.execute(text("select credential from nortpole_integration_use where user_id = :u and integration_id = 'airtable'"), {"u": ann.id}).scalar()
        assert raw is not None and SECRET not in raw and "access_token" not in raw, "the stored text must not hold the token"
        assert raw.startswith("gAAAA"), "it is a sealed token"
    for action in ("integration.install", "integration.connect", "tool.call"):
        for row in audit_rows(action, "airtable"):
            assert SECRET not in json.dumps({"s": row.summary, "d": row.details}), f"{action} row leaked the credential"
    assert audit_rows("integration.connect", "airtable"), "connecting is audited"


def test_disconnect_and_remove(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = person(s, world, "ann")
        s.add(NortPoleSourceRequest(kind="plugin", item_key="airtable", item_name="Airtable", reason="", state="approved", requested_by_id=ann.id, requested_by_email=ann.email))
        s.commit()
        service.install(s, ann, "airtable")
        service.connect(s, ann, "airtable", {"access_token": SECRET})
        assert service.disconnect(s, ann, "airtable")["state"] == "installed"
        refused("not_connected", service.call, s, ann, "airtable", "list_bases", transport=fake({}))
        service.connect(s, ann, "airtable", {"access_token": SECRET})
        service.remove(s, ann, "airtable")
        assert service.status(s, ann, "airtable")["state"] == "available"
        assert s.scalar(select(NortPoleIntegrationUse.id).where(NortPoleIntegrationUse.user_id == ann.id, NortPoleIntegrationUse.integration_id == "airtable")) is None


def test_connecting_needs_the_integration_installed_and_an_account_to_connect(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = person(s, world, "ann")
        refused("not_installed", service.connect, s, ann, "airtable", {"access_token": SECRET})
        service.install(s, ann, "wikipedia")
        refused("no_account_needed", service.connect, s, ann, "wikipedia", {"access_token": SECRET})


def test_blocked_stops_install_connect_and_calls_even_after_install(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = person(s, world, "ann")
        service.install(s, ann, "wikipedia")
        policy.save(policy.PolicyConfig(integrations={"wikipedia": "blocked"}))
        refused("blocked", service.call, s, ann, "wikipedia", "search", model_params={"query": "x"}, transport=fake({}))
        refused("blocked", service.install, s, person(s, world, "bob"), "wikipedia")
        assert service.status(s, ann, "wikipedia")["policy"] == "blocked"


def test_a_category_policy_can_allow_what_the_definition_would_hold_for_approval(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = person(s, world, "ann")
        policy.save(policy.PolicyConfig(categories={"horizontal/automations": "allowed"}))
        assert service.install(s, ann, "airtable")["state"] == "installed"
        policy.save(policy.PolicyConfig(categories={"horizontal/automations": "allowed"}, integrations={"airtable": "blocked"}))
        refused("blocked", service.call, s, ann, "airtable", "list_bases", transport=fake({}))


def test_an_unknown_integration_or_action_is_refused(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = person(s, world, "ann")
        refused("unknown_integration", service.install, s, ann, "nope")
        service.install(s, ann, "wikipedia")
        refused("unknown_action", service.call, s, ann, "wikipedia", "delete_everything", transport=fake({}))


def test_without_a_secrets_key_an_account_is_refused_not_stored_in_the_clear(world, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv(secrets.ENV)
    with get_session_with_current_tenant() as s:
        ann = person(s, world, "ann")
        policy.save(policy.PolicyConfig(integrations={"airtable": "allowed"}))
        service.install(s, ann, "airtable")
        refused("secrets_key_missing", service.connect, s, ann, "airtable", {"access_token": SECRET})
        assert service.status(s, ann, "airtable")["state"] == "installed"
        raw = s.execute(text("select credential from nortpole_integration_use where user_id = :u"), {"u": ann.id}).scalar()
        assert raw is None


def test_a_changed_key_means_connect_again_not_a_crash(world, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = person(s, world, "ann")
        policy.save(policy.PolicyConfig(integrations={"airtable": "allowed"}))
        service.install(s, ann, "airtable")
        service.connect(s, ann, "airtable", {"access_token": SECRET})
        monkeypatch.setenv(secrets.ENV, secrets.generate_key())
        err = refused("not_connected", service.call, s, ann, "airtable", "list_bases", transport=fake({}))
        assert SECRET not in str(err)
