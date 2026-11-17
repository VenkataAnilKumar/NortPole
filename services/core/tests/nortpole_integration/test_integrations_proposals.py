"""Changes an assistant proposes in chat, and the person's yes, on the real database (decision 0008)."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.audit import NortPoleAuditEvent
from nortpole.knowledge.source_requests.models import NortPoleSourceRequest
from nortpole.work.integrations import api, policy, proposals, registry, secrets, service
from nortpole.work.integrations.models import NortPoleIntegrationProposal, NortPoleIntegrationUse
from nortpole.work.integrations.service import IntegrationAccessError
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]
SECRET = f"tok-PROP-{TAG}"
PRIVATE = f"private-note-{TAG}"
ARGS = {"baseId": "appX", "tableId": "tblX", "fields": {"Notes": PRIVATE}}


@pytest.fixture()
def world(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv(secrets.ENV, secrets.generate_key())
    registry.reload()
    saved = policy.load()
    policy.save(policy.PolicyConfig())
    with get_session_with_current_tenant() as s:
        ann = User(id=uuid.uuid4(), email=f"prop-ann-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        bob = User(id=uuid.uuid4(), email=f"prop-bob-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add_all([ann, bob])
        s.commit()
        ids = {"ann": ann.id, "bob": bob.id}
        s.add(NortPoleSourceRequest(kind="plugin", item_key="integration:airtable", item_name="Airtable", reason="", state="approved", requested_by_id=ann.id, requested_by_email=ann.email))
        s.commit()
        service.install(s, ann, "airtable")
        service.connect(s, ann, "airtable", {"access_token": SECRET})
    yield ids
    policy.save(saved)
    with get_session_with_current_tenant() as s:
        for uid in ids.values():
            s.query(NortPoleIntegrationProposal).filter_by(user_id=uid).delete()
            s.query(NortPoleIntegrationUse).filter_by(user_id=uid).delete()
            s.query(NortPoleSourceRequest).filter_by(requested_by_id=uid).delete()
            s.query(User).filter_by(id=uid).delete()
        s.commit()


def fake(body=None, status=200):  # type: ignore[no-untyped-def]
    seen = []

    def transport(request):  # type: ignore[no-untyped-def]
        seen.append(request)
        return status, json.dumps(body or {"id": "recNEW", "fields": {}}).encode(), "application/json"

    transport.seen = seen  # type: ignore[attr-defined]
    return transport


def refused(code, fn, *a, **k):  # type: ignore[no-untyped-def]
    with pytest.raises(IntegrationAccessError) as err:
        fn(*a, **k)
    assert err.value.code == code
    return err.value


def propose(s, user, args=None):  # type: ignore[no-untyped-def]
    return proposals.propose(s, user, "airtable", "create_record", dict(args or ARGS))


def test_a_proposal_is_stored_sealed_checked_and_audited_without_its_content(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        row = propose(s, ann)
        assert row.state == "pending" and row.summary == "Create record in Airtable" and row.expires_at > datetime.now(timezone.utc)
        raw = s.execute(text("select arguments from nortpole_integration_proposal where id = :i"), {"i": row.id}).scalar()
        assert PRIVATE not in raw and "fields" not in raw, "the arguments are sealed at rest"
        mine = proposals.view(row)
        assert mine["arguments"] == ARGS, "the owner sees exactly what would be sent"
        rows = [r for r in s.scalars(select(NortPoleAuditEvent).where(NortPoleAuditEvent.action == "integration.write_proposed")).all() if str(row.id) in json.dumps(r.details or {})]
        assert rows and PRIVATE not in json.dumps({"s": rows[0].summary, "d": rows[0].details}), "the audit row never holds the content"


def test_a_proposal_that_could_never_run_is_refused_when_it_is_made(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        with pytest.raises(executor_error()):
            proposals.propose(s, ann, "airtable", "create_record", {"baseId": "appX"})  # table and fields missing
        refused("not_a_write", proposals.propose, s, ann, "airtable", "list_bases", {})
        refused("not_installed", proposals.propose, s, ann, "hubspot", "create_contact", {"properties": {"email": "a@b.c"}})
        with pytest.raises(executor_error()):
            proposals.propose(s, ann, "airtable", "create_record", {**ARGS, "fields": {"a": "x" * 30_000}})  # the executor's own size limit
        assert s.query(NortPoleIntegrationProposal).filter_by(user_id=ann.id).count() == 0


def executor_error():  # type: ignore[no-untyped-def]
    from nortpole.work.integrations.executor import IntegrationCallError

    return IntegrationCallError


def test_approving_runs_exactly_what_was_stored_once(world) -> None:  # type: ignore[no-untyped-def]
    transport = fake()
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        row = propose(s, ann)
        done = proposals.approve(s, ann, row.id, transport=transport)
        assert done.state == "executed" and done.outcome == "returned"
        assert len(transport.seen) == 1  # type: ignore[attr-defined]
        sent = transport.seen[0]  # type: ignore[attr-defined]
        assert sent.method == "POST" and sent.url == "https://api.airtable.com/v0/appX/tblX" and sent.body == {"fields": {"Notes": PRIVATE}}
        assert sent.headers["Authorization"] == f"Bearer {SECRET}"
        refused("not_pending", proposals.approve, s, ann, row.id, transport=transport)
        assert len(transport.seen) == 1, "a second approval never sends it again"  # type: ignore[attr-defined]
        refused("not_pending", proposals.decline, s, ann, row.id)


def test_declining_sends_nothing_and_cannot_be_undone(world) -> None:  # type: ignore[no-untyped-def]
    transport = fake()
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        row = propose(s, ann)
        assert proposals.decline(s, ann, row.id).state == "declined"
        refused("not_pending", proposals.approve, s, ann, row.id, transport=transport)
        assert transport.seen == []  # type: ignore[attr-defined]


def test_only_the_owner_can_see_or_decide_a_proposal(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann, bob = s.get(User, world["ann"]), s.get(User, world["bob"])
        row = propose(s, ann)
        assert proposals.list_mine(s, bob) == []
        refused("unknown_proposal", proposals.approve, s, bob, row.id, transport=fake())
        refused("unknown_proposal", proposals.decline, s, bob, row.id)
        assert [r.id for r in proposals.list_mine(s, ann)] == [row.id]


def test_a_policy_block_an_expiry_or_a_new_version_stops_an_approved_proposal(world) -> None:  # type: ignore[no-untyped-def]
    transport = fake()
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        blocked, expired, changed = propose(s, ann), propose(s, ann), propose(s, ann)
        policy.save(policy.PolicyConfig(integrations={"airtable": "blocked"}))
        done = proposals.approve(s, ann, blocked.id, transport=transport)
        assert done.state == "failed" and done.outcome == "blocked", "every policy check is made again at approval"
        policy.save(policy.PolicyConfig())
        expired.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        s.commit()
        refused("not_pending", proposals.approve, s, ann, expired.id, transport=transport)
        s.refresh(expired)
        assert expired.state == "expired"
        changed.integration_version = "0.0.1"
        s.commit()
        assert proposals.approve(s, ann, changed.id, transport=transport).outcome == "changed"
        assert transport.seen == []  # type: ignore[attr-defined]


def test_the_number_of_waiting_proposals_is_capped(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        ann = s.get(User, world["ann"])
        for _ in range(proposals.MAX_PENDING):
            propose(s, ann)
        refused("too_many", propose, s, ann)


def test_the_routes_list_approve_and_decline_without_leaking_the_account(world, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from nortpole.work.integrations import executor

    transport = fake()
    real_run = executor.run
    monkeypatch.setattr(executor, "run", lambda *a, **k: real_run(*a, **{**k, "transport": transport}))
    with get_session_with_current_tenant() as s:
        ann, bob = s.get(User, world["ann"]), s.get(User, world["bob"])
        first, second = propose(s, ann), propose(s, ann)
        listed = api.list_proposals(user=ann, db=s)
        assert [i.state for i in listed.items] == ["pending", "pending"] and listed.items[0].arguments == ARGS
        assert SECRET not in listed.model_dump_json()
        ok = api.approve_proposal(first.id, user=ann, db=s)
        assert ok.state == "executed" and SECRET not in ok.model_dump_json()
        assert api.decline_proposal(second.id, user=ann, db=s).state == "declined"
        for fn in (api.approve_proposal, api.decline_proposal):
            with pytest.raises(NortPoleError) as err:
                fn(first.id, user=ann, db=s)
            assert err.value.error_code == NortPoleErrorCode.CONFLICT
            with pytest.raises(NortPoleError) as err2:
                fn(first.id, user=bob, db=s)
            assert err2.value.error_code == NortPoleErrorCode.NOT_FOUND
        assert len(transport.seen) == 1  # type: ignore[attr-defined]
