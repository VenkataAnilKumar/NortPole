"""A destination can require a second person to approve the same payload before anything is sent."""

import json
import uuid

import pytest
from sqlalchemy import text

from evolvxsi.work.actions import api as actions
from evolvxsi.work.actions.models import EvolvXSIAction, EvolvXSIActionTarget
from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.models import User, User__UserGroup
from evolvxsi.error_handling.exceptions import EvolvXSIError
from tests.evolvxsi_integration.test_actions import _approved_task, sink, target  # noqa: F401  (fixtures)
from tests.evolvxsi_integration.test_task_approval_export import world  # noqa: F401  (fixture)
from tests.evolvxsi_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the action tables")

TAG = uuid.uuid4().hex[:8]


def _user(s, name: str, group_id=None):  # type: ignore[no-untyped-def]
    u = User(id=uuid.uuid4(), email=f"second-{name}-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
    s.add(u)
    s.flush()
    if group_id:
        s.add(User__UserGroup(user_id=u.id, user_group_id=group_id))
    s.commit()
    return u


@pytest.fixture()
def people(world):  # type: ignore[no-untyped-def]
    """A second person who can open the cited source (same group) and one who cannot."""
    with get_session_with_current_tenant() as s:
        ok = _user(s, "ok", world["g"])
        blind = _user(s, "blind")
        ids = (ok.id, blind.id)
    yield ids
    with get_session_with_current_tenant() as s:
        s.query(EvolvXSIAction).filter(EvolvXSIAction.second_approver_id.in_(ids)).update({"second_approver_id": None}, synchronize_session=False)
        s.query(User__UserGroup).filter(User__UserGroup.user_id.in_(ids)).delete(synchronize_session=False)
        s.execute(text("delete from evolvxsi_audit_event where actor_email like :p and row_hash is null"), {"p": f"second-%-{TAG}@example.com"})
        s.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        s.commit()


def _require_second(tid: int, on: bool = True) -> None:
    with get_session_with_current_tenant() as s:
        s.query(EvolvXSIActionTarget).filter_by(id=tid).update({"require_second_approval": on})
        s.commit()


def _owner_approved_waiting(s, world, tid):  # type: ignore[no-untyped-def]
    u, t = _approved_task(s, world["u"])
    a = actions.propose_action(t.id, actions.Propose(target_id=tid), user=u, db_session=s)
    a = actions.approve_action(a.id, actions.ApproveAction(version=a.version, fingerprint=a.fingerprint), user=u, db_session=s)
    return u, a


def test_the_owners_approval_alone_does_not_send(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    _require_second(target)
    with get_session_with_current_tenant() as s:
        u, a = _owner_approved_waiting(s, world, target)
        assert a.state == "awaiting_second" and a.needs_second_approval and not a.second_approved
        with pytest.raises(EvolvXSIError) as err:
            actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
        assert "second person" in err.value.detail
    assert sink.requests == []


def test_a_different_person_can_approve_and_then_it_sends_once(world, target, sink, people) -> None:  # type: ignore[no-untyped-def]
    _require_second(target)
    with get_session_with_current_tenant() as s:
        u, a = _owner_approved_waiting(s, world, target)
        second = s.get(User, people[0])
        seen = actions.second_review(a.id, user=second, db_session=s)
        assert "Receipts are due in 30 days" in seen.payload["markdown"]
        done = actions.second_approve(a.id, actions.ApproveAction(version=a.version, fingerprint=a.fingerprint), user=second, db_session=s)
        assert done.state == "approved" and done.second_approved
        sent = actions.execute_action(a.id, actions.VersionOnly(version=done.version), user=u, db_session=s)
        assert sent.state == "succeeded"
        row = s.get(EvolvXSIAction, a.id)
        assert row.second_approver_id == second.id and row.second_approver_id != row.owner_id and row.approved_at is not None
    assert len(sink.requests) == 1


def test_the_owner_cannot_be_their_own_second_approver(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    _require_second(target)
    with get_session_with_current_tenant() as s:
        u, a = _owner_approved_waiting(s, world, target)
        for call in (lambda: actions.second_review(a.id, user=u, db_session=s),
                     lambda: actions.second_approve(a.id, actions.ApproveAction(version=a.version, fingerprint=a.fingerprint), user=u, db_session=s),
                     lambda: actions.second_decline(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)):
            with pytest.raises(EvolvXSIError):
                call()
        assert s.get(EvolvXSIAction, a.id).state == "awaiting_second"
        denied = s.execute(text("select count(*) from evolvxsi_audit_event where action='action.approve' and outcome='denied' and summary like '%the approver is the owner%'")).scalar()
        assert denied >= 3
    assert sink.requests == []


def test_a_second_person_who_cannot_open_a_cited_source_cannot_read_or_approve(world, target, sink, people) -> None:  # type: ignore[no-untyped-def]
    _require_second(target)
    with get_session_with_current_tenant() as s:
        u, a = _owner_approved_waiting(s, world, target)
        blind = s.get(User, people[1])
        with pytest.raises(EvolvXSIError) as err:
            actions.second_review(a.id, user=blind, db_session=s)
        assert "cannot open a source" in err.value.detail
        with pytest.raises(EvolvXSIError):
            actions.second_approve(a.id, actions.ApproveAction(version=a.version, fingerprint=a.fingerprint), user=blind, db_session=s)
        assert s.get(EvolvXSIAction, a.id).state == "awaiting_second"
    assert sink.requests == []


def test_the_second_approval_must_name_the_exact_payload_and_version(world, target, people) -> None:  # type: ignore[no-untyped-def]
    _require_second(target)
    with get_session_with_current_tenant() as s:
        u, a = _owner_approved_waiting(s, world, target)
        second = s.get(User, people[0])
        with pytest.raises(EvolvXSIError):
            actions.second_approve(a.id, actions.ApproveAction(version=a.version, fingerprint="0" * 64), user=second, db_session=s)
        with pytest.raises(EvolvXSIError):
            actions.second_approve(a.id, actions.ApproveAction(version=a.version + 5, fingerprint=a.fingerprint), user=second, db_session=s)
        assert s.get(EvolvXSIAction, a.id).state == "awaiting_second"


def test_declining_cancels_and_nothing_is_sent(world, target, sink, people) -> None:  # type: ignore[no-untyped-def]
    _require_second(target)
    with get_session_with_current_tenant() as s:
        u, a = _owner_approved_waiting(s, world, target)
        second = s.get(User, people[0])
        out = actions.second_decline(a.id, actions.VersionOnly(version=a.version), user=second, db_session=s)
        assert out.state == "cancelled"
        with pytest.raises(EvolvXSIError):
            actions.execute_action(a.id, actions.VersionOnly(version=out.version), user=u, db_session=s)
    assert sink.requests == []


def test_the_owner_can_cancel_while_waiting(world, target) -> None:  # type: ignore[no-untyped-def]
    _require_second(target)
    with get_session_with_current_tenant() as s:
        u, a = _owner_approved_waiting(s, world, target)
        assert actions.cancel_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s).state == "cancelled"


def test_turning_the_rule_on_stops_an_older_approval(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _approved_task(s, world["u"])
        a = actions.propose_action(t.id, actions.Propose(target_id=target), user=u, db_session=s)
        a = actions.approve_action(a.id, actions.ApproveAction(version=a.version, fingerprint=a.fingerprint), user=u, db_session=s)
        assert a.state == "approved"  # approved while no second person was required
    _require_second(target)
    with get_session_with_current_tenant() as s:
        u = s.get(User, world["u"])
        with pytest.raises(EvolvXSIError) as err:
            actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
        assert "second person" in err.value.detail
    assert sink.requests == []


def test_the_queue_leaves_out_the_callers_own_and_holds_no_draft_text(world, target, people) -> None:  # type: ignore[no-untyped-def]
    _require_second(target)
    with get_session_with_current_tenant() as s:
        u, a = _owner_approved_waiting(s, world, target)
        second = s.get(User, people[0])
        mine = {x.id for x in actions.awaiting_second(user=u, db_session=s)}
        theirs = actions.awaiting_second(user=second, db_session=s)
        assert a.id not in mine and a.id in {x.id for x in theirs}
        text_out = json.dumps([x.model_dump(mode="json") for x in theirs])
        assert "Receipts are due" not in text_out and "markdown" not in text_out, "the queue shows no draft text"


def test_opening_a_draft_for_review_is_audited_without_its_text(world, target, people) -> None:  # type: ignore[no-untyped-def]
    _require_second(target)
    with get_session_with_current_tenant() as s:
        u, a = _owner_approved_waiting(s, world, target)
        second = s.get(User, people[0])
        actions.second_review(a.id, user=second, db_session=s)
        rows = s.execute(text("select summary, details::text from evolvxsi_audit_event where action='action.second_review' and resource_id=:i"), {"i": str(a.id)}).all()
        assert len(rows) == 1 and "Receipts are due" not in rows[0][0] + (rows[0][1] or "")


def test_a_target_without_the_rule_still_works_as_before(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _approved_task(s, world["u"])
        a = actions.propose_action(t.id, actions.Propose(target_id=target), user=u, db_session=s)
        a = actions.approve_action(a.id, actions.ApproveAction(version=a.version, fingerprint=a.fingerprint), user=u, db_session=s)
        assert a.state == "approved" and not a.needs_second_approval
        assert actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s).state == "succeeded"
    assert len(sink.requests) == 1
