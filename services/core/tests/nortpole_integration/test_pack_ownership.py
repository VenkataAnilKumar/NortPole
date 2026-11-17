"""A pack belongs to the signer of its newest version (decision on the pack takeover gap), on the real database."""

import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.work.packs import api as packs
from nortpole.work.packs import ownership
from nortpole.work.packs.models import NortPolePackSigner, NortPolePackTransfer, NortPolePackVersion
from tests.nortpole_integration.test_packs import ADMIN, PACK_ID, _b64pub, _manifest, _package, signer  # noqa: F401
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the pack tables")


@pytest.fixture()
def rival():  # type: ignore[no-untyped-def]
    key, key_id = Ed25519PrivateKey.generate(), f"rival-{uuid.uuid4().hex[:8]}"
    with get_session_with_current_tenant() as s:
        packs.add_signer(packs.SignerIn(key_id=key_id, public_key=_b64pub(key), label="rival"), user=ADMIN, db_session=s)
    yield key, key_id
    with get_session_with_current_tenant() as s:
        s.query(NortPolePackTransfer).filter_by(pack_id=PACK_ID).delete()
        s.query(NortPolePackVersion).filter_by(pack_id=PACK_ID).delete()
        s.query(NortPolePackSigner).filter_by(key_id=key_id).delete()
        s.execute(text("delete from nortpole_audit_event where actor_email = :e and row_hash is null"), {"e": ADMIN.email})
        s.commit()


def refused(fn, *a, **k):  # type: ignore[no-untyped-def]
    with pytest.raises(NortPoleError) as err:
        fn(*a, **k)
    return err.value


def test_another_trusted_signer_cannot_publish_a_new_version_of_a_pack_it_does_not_own(signer, rival) -> None:  # type: ignore[no-untyped-def]
    key, key_id = signer
    rkey, rid = rival
    with get_session_with_current_tenant() as s:
        packs.install_pack(_package(key, key_id, _manifest("1.0.0")), user=ADMIN, db_session=s)
        assert ownership.owner_of(s, PACK_ID) == key_id
        err = refused(packs.install_pack, _package(rkey, rid, _manifest("1.0.1", description="The rival's content.")), user=ADMIN, db_session=s)
        assert err.error_code == NortPoleErrorCode.CONFLICT and key_id in err.detail and "key change" in err.detail
        assert s.query(NortPolePackVersion).filter_by(pack_id=PACK_ID).count() == 1, "nothing of the rival's was stored"
        denied = s.execute(text("select count(*) from nortpole_audit_event where action='pack.install' and outcome='denied' and actor_email = :e and summary like '%belongs to another signer%'"), {"e": ADMIN.email}).scalar()
        assert denied >= 1, "the refusal is audited"
        # The owner is unaffected and can keep publishing.
        packs.install_pack(_package(key, key_id, _manifest("1.0.2")), user=ADMIN, db_session=s)
        assert ownership.owner_of(s, PACK_ID) == key_id


def test_an_administrator_can_approve_a_key_change_which_is_spent_by_one_publish(signer, rival) -> None:  # type: ignore[no-untyped-def]
    key, key_id = signer
    rkey, rid = rival
    with get_session_with_current_tenant() as s:
        packs.install_pack(_package(key, key_id, _manifest("1.0.0")), user=ADMIN, db_session=s)
        view = packs.approve_key_change(PACK_ID, packs.TransferIn(to_key_id=rid), user=ADMIN, db_session=s)
        assert view.owner_key_id == key_id and view.to_key_id == rid
        packs.install_pack(_package(rkey, rid, _manifest("1.1.0")), user=ADMIN, db_session=s)
        assert ownership.owner_of(s, PACK_ID) == rid, "the new signer now owns the pack"
        assert s.get(NortPolePackTransfer, PACK_ID) is None, "the approval was spent"
        # The old signer is now the one who needs an approval.
        err = refused(packs.install_pack, _package(key, key_id, _manifest("1.2.0")), user=ADMIN, db_session=s)
        assert err.error_code == NortPoleErrorCode.CONFLICT


def test_a_key_change_must_name_a_trusted_unrevoked_different_signer_and_can_be_cancelled(signer, rival) -> None:  # type: ignore[no-untyped-def]
    key, key_id = signer
    rkey, rid = rival
    with get_session_with_current_tenant() as s:
        assert refused(packs.approve_key_change, PACK_ID, packs.TransferIn(to_key_id=rid), user=ADMIN, db_session=s).error_code == NortPoleErrorCode.NOT_FOUND, "a pack with no version has no owner"
        packs.install_pack(_package(key, key_id, _manifest("1.0.0")), user=ADMIN, db_session=s)
        assert refused(packs.approve_key_change, PACK_ID, packs.TransferIn(to_key_id="nobody"), user=ADMIN, db_session=s).error_code == NortPoleErrorCode.INVALID_INPUT
        assert refused(packs.approve_key_change, PACK_ID, packs.TransferIn(to_key_id=key_id), user=ADMIN, db_session=s).error_code == NortPoleErrorCode.INVALID_INPUT
        packs.approve_key_change(PACK_ID, packs.TransferIn(to_key_id=rid), user=ADMIN, db_session=s)
        assert packs.cancel_key_change(PACK_ID, user=ADMIN, db_session=s) == {"cancelled": True}
        assert refused(packs.install_pack, _package(rkey, rid, _manifest("1.1.0")), user=ADMIN, db_session=s).error_code == NortPoleErrorCode.CONFLICT
        assert refused(packs.cancel_key_change, PACK_ID, user=ADMIN, db_session=s).error_code == NortPoleErrorCode.NOT_FOUND


def test_an_approval_for_one_signer_does_not_let_another_through(signer, rival) -> None:  # type: ignore[no-untyped-def]
    key, key_id = signer
    rkey, rid = rival
    third, third_id = Ed25519PrivateKey.generate(), f"third-{uuid.uuid4().hex[:8]}"
    with get_session_with_current_tenant() as s:
        packs.add_signer(packs.SignerIn(key_id=third_id, public_key=_b64pub(third), label="third"), user=ADMIN, db_session=s)
        try:
            packs.install_pack(_package(key, key_id, _manifest("1.0.0")), user=ADMIN, db_session=s)
            packs.approve_key_change(PACK_ID, packs.TransferIn(to_key_id=rid), user=ADMIN, db_session=s)
            assert refused(packs.install_pack, _package(third, third_id, _manifest("1.1.0")), user=ADMIN, db_session=s).error_code == NortPoleErrorCode.CONFLICT
        finally:
            s.query(NortPolePackSigner).filter_by(key_id=third_id).delete()
            s.commit()


def test_rotation_after_revoking_the_old_key_still_works_without_an_approval(signer, rival) -> None:  # type: ignore[no-untyped-def]
    key, key_id = signer
    rkey, rid = rival
    with get_session_with_current_tenant() as s:
        packs.install_pack(_package(key, key_id, _manifest("1.0.0")), user=ADMIN, db_session=s)
        assert refused(packs.install_pack, _package(rkey, rid, _manifest("1.1.0")), user=ADMIN, db_session=s).error_code == NortPoleErrorCode.CONFLICT
        s.get(NortPolePackSigner, key_id).revoked = True
        s.commit()
        packs.install_pack(_package(rkey, rid, _manifest("1.1.0")), user=ADMIN, db_session=s)
        assert ownership.owner_of(s, PACK_ID) == rid
