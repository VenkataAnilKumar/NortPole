"""The second-administrator rule for send destinations: registering one or changing where drafts may go waits for a
second administrator when the rule is on."""

import json
import uuid

import pytest
from sqlalchemy import text

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.admin_changes import controls, service as changes
from nortpole.governance.admin_changes.models import NortPoleAdminChange
from nortpole.work.actions import api as actions
from nortpole.work.actions.models import NortPoleActionTarget
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the action tables")

TAG = uuid.uuid4().hex[:8]


@pytest.fixture()
def world():  # type: ignore[no-untyped-def]
    original = controls.load()
    with get_session_with_current_tenant() as s:
        a = User(id=uuid.uuid4(), email=f"dest-a-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        b = User(id=uuid.uuid4(), email=f"dest-b-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add_all([a, b])
        s.commit()
        ids = (a.id, b.id)
    controls.save(controls.AdminControls(version=original.version + 1, second_for_destinations=True))
    yield ids
    controls.save(original.model_copy(update={"version": controls.load().version + 1}))
    with get_session_with_current_tenant() as s:
        s.query(NortPoleAdminChange).filter(NortPoleAdminChange.proposed_by_id.in_(ids)).delete(synchronize_session=False)
        s.query(NortPoleActionTarget).filter(NortPoleActionTarget.name.like(f"%{TAG}")).delete(synchronize_session=False)
        for uid in ids:
            s.execute(text("delete from nortpole_audit_event where actor_user_id = :u and row_hash is null"), {"u": str(uid)})
            s.query(User).filter_by(id=uid).delete()
        s.commit()


def _body(name: str, url: str = "mailto:finance@example.com") -> actions.TargetIn:
    return actions.TargetIn(name=name, kind="email", url=url, allowed_data_classes=["internal"])


def _cid(response) -> str:  # type: ignore[no-untyped-def]
    assert response.status_code == 202
    return json.loads(response.body)["change_id"]


def test_a_new_destination_and_a_change_wait_for_a_second_administrator(world) -> None:  # type: ignore[no-untyped-def]
    a_id, b_id = world
    name = f"hook-{TAG}"
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, a_id), s.get(User, b_id)
        cid = _cid(actions.create_target(_body(name), user=a, db_session=s))
        assert s.query(NortPoleActionTarget).filter_by(name=name).count() == 0
        with pytest.raises(NortPoleError) as same:
            changes.approve(s, a, cid)
        assert same.value.error_code == NortPoleErrorCode.INSUFFICIENT_PERMISSIONS
        assert changes.approve(s, b, cid).state == "applied"
        target = s.query(NortPoleActionTarget).filter_by(name=name).one()
        # Pointing it somewhere else is held too, and the old address stays until approved.
        cid2 = _cid(actions.update_target(target.id, _body(name, "mailto:audit@example.com"), user=a, db_session=s))
        s.expire_all()
        assert s.get(NortPoleActionTarget, target.id).url == "mailto:finance@example.com"
        changes.approve(s, b, cid2)
        s.expire_all()
        assert s.get(NortPoleActionTarget, target.id).url == "mailto:audit@example.com"


def test_a_bad_destination_is_refused_when_proposed_and_a_declined_one_never_exists(world) -> None:  # type: ignore[no-untyped-def]
    a_id, b_id = world
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, a_id), s.get(User, b_id)
        with pytest.raises(NortPoleError) as err:
            actions.create_target(_body(f"bad-{TAG}", "not-an-address"), user=a, db_session=s)
        assert err.value.error_code == NortPoleErrorCode.INVALID_INPUT
        cid = _cid(actions.create_target(_body(f"no-{TAG}"), user=a, db_session=s))
        assert changes.decline(s, b, cid).state == "declined"
        assert s.query(NortPoleActionTarget).filter_by(name=f"no-{TAG}").count() == 0


def test_with_the_rule_off_a_destination_is_registered_at_once() -> None:
    original = controls.load()
    controls.save(original.model_copy(update={"version": original.version + 1, "second_for_destinations": False}))
    try:
        with get_session_with_current_tenant() as s:
            u = User(id=uuid.uuid4(), email=f"dest-c-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
            s.add(u)
            s.commit()
            try:
                view = actions.create_target(_body(f"now-{TAG}"), user=u, db_session=s)
                assert view.name == f"now-{TAG}"
            finally:
                s.query(NortPoleActionTarget).filter(NortPoleActionTarget.name.like(f"%{TAG}")).delete(synchronize_session=False)
                s.execute(text("delete from nortpole_audit_event where actor_user_id = :u and row_hash is null"), {"u": str(u.id)})
                s.query(User).filter_by(id=u.id).delete()
                s.commit()
    finally:
        controls.save(original.model_copy(update={"version": controls.load().version + 1}))
