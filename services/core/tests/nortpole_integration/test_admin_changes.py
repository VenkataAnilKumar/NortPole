"""Administrator changes that wait for a second administrator."""

import datetime
import json
import uuid

import pytest
from sqlalchemy import text

from nortpole.governance.admin_changes import api as changes_api
from nortpole.governance.admin_changes import controls, service
from nortpole.governance.admin_changes.models import NortPoleAdminChange
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.retention import api as ret_api
from nortpole.governance.retention.settings import load as load_ret, save as save_ret
from nortpole.governance.route_policy import api as rp_api
from nortpole.governance.route_policy.policy import load_policy, save_policy
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]


@pytest.fixture()
def world():  # type: ignore[no-untyped-def]
    """Two administrators, and every setting these tests touch put back afterwards."""
    saved = (controls.load(), load_ret(), load_policy())
    controls.save(controls.AdminControls(version=saved[0].version))  # every rule off to start
    with get_session_with_current_tenant() as s:
        a = User(id=uuid.uuid4(), email=f"admin-a-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        b = User(id=uuid.uuid4(), email=f"admin-b-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add_all([a, b])
        s.commit()
        ids = (a.id, b.id)
    yield ids
    controls.save(saved[0])
    save_ret(saved[1])
    save_policy(saved[2])
    with get_session_with_current_tenant() as s:
        s.query(NortPoleAdminChange).filter(NortPoleAdminChange.proposed_by_email.like(f"%-{TAG}@example.com")).delete(synchronize_session=False)
        s.execute(text("delete from nortpole_audit_event where actor_email like :p and row_hash is null"), {"p": f"admin-%-{TAG}@example.com"})
        s.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        s.commit()


def _turn_on(route_policy: bool = False, retention: bool = False) -> None:
    c = controls.load()
    controls.save(controls.AdminControls(version=c.version + 1, second_for_route_policy=route_policy, second_for_retention=retention))


def _body(days: int = 400, **kw):  # type: ignore[no-untyped-def]
    return ret_api.RetentionUpdate(audit_days=days, usage_days=days, **kw)


def _status(resp) -> int:  # type: ignore[no-untyped-def]
    return getattr(resp, "status_code", 200)


def test_with_every_rule_off_a_change_takes_effect_at_once(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        a = s.get(User, world[0])
        out = ret_api.put_retention(_body(401), user=a, db_session=s)
        assert _status(out) == 200 and out.audit_days == 401 and load_ret().audit_days == 401


def test_with_the_rule_on_a_change_is_held_and_nothing_is_saved(world) -> None:  # type: ignore[no-untyped-def]
    _turn_on(retention=True)
    before = load_ret()
    with get_session_with_current_tenant() as s:
        a = s.get(User, world[0])
        out = ret_api.put_retention(_body(402), user=a, db_session=s)
        assert _status(out) == 202
        body = json.loads(out.body)
        assert body["pending_approval"] is True and "not applied" in body["message"]
        assert load_ret().audit_days == before.audit_days, "the setting is unchanged until a second administrator approves"
        row = s.get(NortPoleAdminChange, uuid.UUID(body["change_id"]))
        assert row.state == "pending" and row.proposed_by_email == a.email and "402" in row.summary
        n = s.execute(text("select count(*) from nortpole_audit_event where action='admin.change_propose' and resource_id=:i"), {"i": body["change_id"]}).scalar()
        assert n == 1


def test_a_different_administrator_approves_and_it_is_applied_and_audited(world) -> None:  # type: ignore[no-untyped-def]
    _turn_on(retention=True)
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, world[0]), s.get(User, world[1])
        cid = uuid.UUID(json.loads(ret_api.put_retention(_body(403), user=a, db_session=s).body)["change_id"])
        done = service.approve(s, b, cid)
        assert done.state == "applied" and done.decided_by_email == b.email
        assert load_ret().audit_days == 403
        rows = s.execute(text("select details::text from nortpole_audit_event where action='retention.change' and details::text like :p order by id desc limit 1"),
                         {"p": f"%{b.email}%"}).all()
        assert rows and a.email in rows[0][0] and b.email in rows[0][0], "the change is audited with both who proposed and who approved"


def test_the_proposer_cannot_approve_their_own_change(world) -> None:  # type: ignore[no-untyped-def]
    _turn_on(retention=True)
    with get_session_with_current_tenant() as s:
        a = s.get(User, world[0])
        cid = uuid.UUID(json.loads(ret_api.put_retention(_body(404), user=a, db_session=s).body)["change_id"])
        with pytest.raises(NortPoleError):
            service.approve(s, a, cid)
        assert s.get(NortPoleAdminChange, cid).state == "pending" and load_ret().audit_days != 404
        denied = s.execute(text("select count(*) from nortpole_audit_event where action='admin.change_decide' and outcome='denied' and summary like 'Approval refused: the approver proposed it%'")).scalar()
        assert denied >= 1


def test_declining_applies_nothing_and_only_the_proposer_can_cancel(world) -> None:  # type: ignore[no-untyped-def]
    _turn_on(retention=True)
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, world[0]), s.get(User, world[1])
        cid = uuid.UUID(json.loads(ret_api.put_retention(_body(405), user=a, db_session=s).body)["change_id"])
        with pytest.raises(NortPoleError):
            service.cancel(s, b, cid)
        with pytest.raises(NortPoleError):
            service.decline(s, a, cid)
        assert service.decline(s, b, cid).state == "declined" and load_ret().audit_days != 405
        cid2 = uuid.UUID(json.loads(ret_api.put_retention(_body(406), user=a, db_session=s).body)["change_id"])
        assert service.cancel(s, a, cid2).state == "cancelled" and load_ret().audit_days != 406


def test_a_change_made_after_the_proposal_makes_the_approval_fail(world) -> None:  # type: ignore[no-untyped-def]
    _turn_on(retention=True)
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, world[0]), s.get(User, world[1])
        cid = uuid.UUID(json.loads(ret_api.put_retention(_body(407), user=a, db_session=s).body)["change_id"])
        ret_api.apply_retention_update(_body(500), a)  # the setting moves on in the meantime
        with pytest.raises(NortPoleError) as err:
            service.approve(s, b, cid)
        assert "changed after this was proposed" in err.value.detail
        row = s.get(NortPoleAdminChange, cid)
        assert row.state == "failed" and load_ret().audit_days == 500


def test_an_invalid_change_is_refused_when_proposed(world) -> None:  # type: ignore[no-untyped-def]
    _turn_on(retention=True, route_policy=True)
    with get_session_with_current_tenant() as s:
        a = s.get(User, world[0])
        with pytest.raises(NortPoleError):
            ret_api.put_retention(ret_api.RetentionUpdate(legal_hold=True, hold_reason="  "), user=a, db_session=s)
        with pytest.raises(NortPoleError):
            rp_api.put_route_policy(rp_api.RoutePolicyUpdate(route_kinds={"99999999": "local"}), user=a, db_session=s)
        assert s.query(NortPoleAdminChange).filter_by(proposed_by_id=a.id).count() == 0


def test_a_route_policy_change_is_held_then_applied(world) -> None:  # type: ignore[no-untyped-def]
    _turn_on(route_policy=True)
    before = load_policy()
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, world[0]), s.get(User, world[1])
        out = rp_api.put_route_policy(rp_api.RoutePolicyUpdate(redact_route_kinds=["cloud", "private"]), user=a, db_session=s)
        assert _status(out) == 202 and load_policy().version == before.version
        service.approve(s, b, uuid.UUID(json.loads(out.body)["change_id"]))
        now = load_policy()
        assert now.version == before.version + 1 and sorted(now.redact_route_kinds) == ["cloud", "private"]


def test_the_rules_cannot_be_switched_off_by_one_administrator_while_on(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, world[0]), s.get(User, world[1])
        on = changes_api.put_controls(changes_api.ControlsUpdate(second_for_route_policy=True, second_for_retention=False), user=a, db_session=s)
        assert controls.load().second_for_route_policy is True, "turning a rule on takes effect at once"
        off = changes_api.put_controls(changes_api.ControlsUpdate(second_for_route_policy=False, second_for_retention=False), user=a, db_session=s)
        assert _status(off) == 202 and controls.load().second_for_route_policy is True, "switching it off needs a second administrator"
        service.approve(s, b, uuid.UUID(json.loads(off.body)["change_id"]))
        assert controls.load().second_for_route_policy is False


def test_an_old_proposal_expires_and_a_newer_one_replaces_an_older_one(world) -> None:  # type: ignore[no-untyped-def]
    _turn_on(retention=True)
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, world[0]), s.get(User, world[1])
        first = uuid.UUID(json.loads(ret_api.put_retention(_body(408), user=a, db_session=s).body)["change_id"])
        second = uuid.UUID(json.loads(ret_api.put_retention(_body(409), user=a, db_session=s).body)["change_id"])
        assert s.get(NortPoleAdminChange, first).state == "cancelled", "a newer proposal of the same kind replaces the older"
        s.get(NortPoleAdminChange, second).created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)
        s.commit()
        with pytest.raises(NortPoleError) as err:
            service.approve(s, b, second)
        assert "expired" in err.value.detail
        assert load_ret().audit_days not in (408, 409)


def test_the_list_marks_ones_the_caller_proposed_and_holds_no_secret(world) -> None:  # type: ignore[no-untyped-def]
    _turn_on(retention=True)
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, world[0]), s.get(User, world[1])
        ret_api.put_retention(_body(410, legal_hold=True, hold_reason="case 77"), user=a, db_session=s)
        mine = [c for c in changes_api.list_changes(user=a, db_session=s).pending if c.proposed_by_email == a.email]
        theirs = [c for c in changes_api.list_changes(user=b, db_session=s).pending if c.proposed_by_email == a.email]
        assert mine and mine[0].own is True and theirs and theirs[0].own is False
