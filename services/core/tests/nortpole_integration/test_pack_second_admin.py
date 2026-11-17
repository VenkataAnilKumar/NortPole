"""The second-administrator rule for packs: trusting a signer, a key change and activating a version wait for a second
administrator when the rule is on; revoking a signer never waits."""

import json
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.admin_changes import controls, service as changes
from nortpole.governance.admin_changes.api import ControlsUpdate, put_controls
from nortpole.governance.admin_changes.models import NortPoleAdminChange
from nortpole.work.packs import api as packs
from nortpole.work.packs import ownership
from nortpole.work.packs.models import NortPolePackSigner, NortPolePackTransfer, NortPolePackVersion
from tests.nortpole_integration.test_packs import PACK_ID, _b64pub, _manifest, _package
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the pack tables")

TAG = uuid.uuid4().hex[:8]


@pytest.fixture()
def world():  # type: ignore[no-untyped-def]
    original = controls.load()
    key, key_id = Ed25519PrivateKey.generate(), f"sa-{TAG}"
    rkey, rid = Ed25519PrivateKey.generate(), f"sa-rival-{TAG}"
    with get_session_with_current_tenant() as s:
        a = User(id=uuid.uuid4(), email=f"sa-a-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        b = User(id=uuid.uuid4(), email=f"sa-b-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add_all([a, b])
        s.commit()
        for k, i in ((key, key_id), (rkey, rid)):
            s.add(NortPolePackSigner(key_id=i, public_key=_b64pub(k), label="t"))
        s.commit()
        ids = (a.id, b.id)
    controls.save(controls.AdminControls(version=original.version + 1, second_for_packs=True))
    yield ids, (key, key_id), (rkey, rid)
    controls.save(original.model_copy(update={"version": controls.load().version + 1}))
    with get_session_with_current_tenant() as s:
        s.query(NortPoleAdminChange).filter(NortPoleAdminChange.proposed_by_id.in_(ids)).delete(synchronize_session=False)
        s.query(NortPolePackTransfer).filter_by(pack_id=PACK_ID).delete()
        s.query(NortPolePackVersion).filter_by(pack_id=PACK_ID).delete()
        s.query(NortPolePackSigner).filter(NortPolePackSigner.key_id.like(f"%{TAG}")).delete(synchronize_session=False)
        for uid in ids:
            s.execute(text("delete from nortpole_audit_event where actor_user_id = :u and row_hash is null"), {"u": str(uid)})
            s.query(User).filter_by(id=uid).delete()
        s.commit()


def change_id(response) -> str:  # type: ignore[no-untyped-def]
    assert response.status_code == 202, response.body
    body = json.loads(response.body)
    assert body["pending_approval"] is True
    return body["change_id"]


def test_trusting_a_signer_waits_for_a_second_administrator(world) -> None:  # type: ignore[no-untyped-def]
    (a_id, b_id), _, _ = world
    new = Ed25519PrivateKey.generate()
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, a_id), s.get(User, b_id)
        with pytest.raises(NortPoleError) as err:
            packs.add_signer(packs.SignerIn(key_id=f"bad-{TAG}", public_key="not a key"), user=a, db_session=s)
        assert err.value.error_code == NortPoleErrorCode.INVALID_INPUT, "a mistake is reported at once, not held"
        body = packs.SignerIn(key_id=f"sa-new-{TAG}", public_key=_b64pub(new), label="held")
        cid = change_id(packs.add_signer(body, user=a, db_session=s))
        assert s.get(NortPolePackSigner, body.key_id) is None, "nothing happens until a second administrator approves"
        with pytest.raises(NortPoleError) as same:
            changes.approve(s, a, cid)
        assert same.value.error_code == NortPoleErrorCode.INSUFFICIENT_PERMISSIONS
        assert changes.approve(s, b, cid).state == "applied"
        assert s.get(NortPolePackSigner, body.key_id) is not None


def test_a_key_change_and_an_activation_wait_and_then_apply_exactly_what_was_proposed(world) -> None:  # type: ignore[no-untyped-def]
    (a_id, b_id), (key, key_id), (rkey, rid) = world
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, a_id), s.get(User, b_id)
        packs.install_pack(_package(key, key_id, _manifest("1.0.0")), user=a, db_session=s)
        # Activation is held.
        cid = change_id(packs.activate(PACK_ID, "1.0.0", user=a, db_session=s))
        assert not s.query(NortPolePackVersion).filter_by(pack_id=PACK_ID, version="1.0.0").one().active
        changes.approve(s, b, cid)
        s.expire_all()
        assert s.query(NortPolePackVersion).filter_by(pack_id=PACK_ID, version="1.0.0").one().active
        # A key change is held, then lets the rival publish once.
        cid2 = change_id(packs.approve_key_change(PACK_ID, packs.TransferIn(to_key_id=rid), user=a, db_session=s))
        assert s.get(NortPolePackTransfer, PACK_ID) is None
        with pytest.raises(NortPoleError):
            packs.install_pack(_package(rkey, rid, _manifest("1.1.0")), user=a, db_session=s)
        changes.approve(s, b, cid2)
        packs.install_pack(_package(rkey, rid, _manifest("1.1.0")), user=a, db_session=s)
        assert ownership.owner_of(s, PACK_ID) == rid


def test_a_declined_change_never_applies_and_a_bad_one_is_refused_when_proposed(world) -> None:  # type: ignore[no-untyped-def]
    (a_id, b_id), (key, key_id), (rkey, rid) = world
    with get_session_with_current_tenant() as s:
        a, b = s.get(User, a_id), s.get(User, b_id)
        packs.install_pack(_package(key, key_id, _manifest("1.0.0")), user=a, db_session=s)
        with pytest.raises(NortPoleError) as e1:
            packs.activate(PACK_ID, "9.9.9", user=a, db_session=s)
        assert e1.value.error_code == NortPoleErrorCode.NOT_FOUND
        with pytest.raises(NortPoleError) as e2:
            packs.approve_key_change(PACK_ID, packs.TransferIn(to_key_id=key_id), user=a, db_session=s)
        assert e2.value.error_code == NortPoleErrorCode.INVALID_INPUT
        cid = change_id(packs.activate(PACK_ID, "1.0.0", user=a, db_session=s))
        assert changes.decline(s, b, cid).state == "declined"
        assert not s.query(NortPolePackVersion).filter_by(pack_id=PACK_ID).one().active


def test_revoking_a_signer_is_never_held_back(world) -> None:  # type: ignore[no-untyped-def]
    (a_id, _), (_, key_id), _ = world
    with get_session_with_current_tenant() as s:
        a = s.get(User, a_id)
        view = packs.revoke_signer(key_id, user=a, db_session=s)
        assert view.revoked is True, "the emergency stop works at once even with the rule on"


def test_the_rule_can_be_turned_on_from_the_controls_and_keeps_its_value_when_left_out(world) -> None:  # type: ignore[no-untyped-def]
    (a_id, _), _, _ = world
    original = controls.load()
    assert original.second_for_packs is True and controls.required("pack_activate") and controls.required("pack_owner") and controls.required("pack_signer")
    assert controls.required("controls"), "with a rule on, changing the rules needs a second administrator"
    with get_session_with_current_tenant() as s:
        a = s.get(User, a_id)
        held = put_controls(ControlsUpdate(second_for_route_policy=False, second_for_retention=False), user=a, db_session=s)
        assert held.status_code == 202, "turning protection down is itself held while a rule is on"
