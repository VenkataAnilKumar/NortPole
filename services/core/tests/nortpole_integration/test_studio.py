"""Studio: administrators write a pack in the product; it is checked, signed with the workspace key and installed inactive."""

import copy
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.key_value_store.factory import get_kv_store
from nortpole.key_value_store.interface import KvKeyNotFoundError
from nortpole.work.packs import studio
from nortpole.work.packs.models import NortPolePackSigner, NortPolePackVersion
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]
PACK = f"studio-{TAG}"
SAMPLE = json.loads((Path(__file__).parents[2] / "tests/common/fixtures/finance-policy-review-1.1.0.json").read_text())


def _kv(key):  # type: ignore[no-untyped-def]
    try:
        return get_kv_store().load(key)
    except KvKeyNotFoundError:
        return None


@pytest.fixture()
def admin():  # type: ignore[no-untyped-def]
    saved_key, saved_drafts = _kv(studio.KEY_KV), _kv(studio.DRAFTS_KV)
    with get_session_with_current_tenant() as s:
        signer_existed = s.get(NortPolePackSigner, studio.KEY_ID) is not None
        revoked_before = s.get(NortPolePackSigner, studio.KEY_ID).revoked if signer_existed else False
        u = User(id=uuid.uuid4(), email=f"studio-{TAG}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add(u)
        s.commit()
        uid = u.id
    yield uid
    store = get_kv_store()
    store.store(studio.DRAFTS_KV, saved_drafts or {})
    with get_session_with_current_tenant() as s:
        s.query(NortPolePackVersion).filter(NortPolePackVersion.pack_id.like(f"%{TAG}")).delete(synchronize_session=False)
        signer = s.get(NortPolePackSigner, studio.KEY_ID)
        if not signer_existed and signer is not None and not s.query(NortPolePackVersion).filter_by(signer_key_id=studio.KEY_ID).count():
            s.delete(signer)
            if saved_key is None:
                store.delete(studio.KEY_KV)
        elif signer is not None:
            signer.revoked = revoked_before
        s.execute(text("delete from evolvxsi_audit_event where actor_email = :e and row_hash is null"), {"e": f"studio-{TAG}@example.com"})
        s.query(User).filter_by(id=uid).delete()
        s.commit()


def _draft(version="1.0.0"):  # type: ignore[no-untyped-def]
    m = copy.deepcopy(SAMPLE)
    m.update({"id": PACK, "version": version, "name": "Studio test pack", "evaluation_cases": []})
    m["agents"] = [{"id": "researcher", "name": "Researcher", "description": "Finds and cites the rule.", "instructions": "Search the policy first.",
                    "tools": ["search"], "max_searches": 2, "guides": ["cite-the-rule"]}]
    m["templates"][0]["agent"] = "researcher"
    return m


def test_problems_are_listed_and_a_draft_with_problems_can_still_be_saved(admin) -> None:  # type: ignore[no-untyped-def]
    bad = _draft()
    bad["agents"][0]["tools"] = ["send_email"]
    bad["templates"][1]["guides"] = ["missing"]
    result = studio.check(bad)
    assert not result.ok and len(result.problems) >= 1 and any("send_email" in p.message or "missing" in p.message for p in result.problems)
    assert studio.save_draft(PACK, studio.Draft(manifest=bad), _=None).ok is False
    assert PACK in studio.list_drafts(_=None)
    with pytest.raises(NortPoleError):
        studio.save_draft("another-id", studio.Draft(manifest=bad), _=None)
    with get_session_with_current_tenant() as s:
        with pytest.raises(NortPoleError):
            studio.publish(PACK, user=s.get(User, admin), db_session=s)
        assert s.query(NortPolePackVersion).filter_by(pack_id=PACK).count() == 0, "a draft with problems is never installed"


def test_publishing_signs_with_the_workspace_key_and_installs_inactive(admin) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u = s.get(User, admin)
        studio.save_draft(PACK, studio.Draft(manifest=_draft("1.0.0")), _=None)
        v = studio.publish(PACK, user=u, db_session=s)
        assert (v.pack_id, v.version, v.active, v.signer_key_id) == (PACK, "1.0.0", False, studio.KEY_ID)
        assert [a.name for a in v.agents] == ["Researcher"] and v.agents[0].instructions == "Search the policy first."
        assert s.get(NortPolePackSigner, studio.KEY_ID) is not None, "the workspace signer is trusted on first use"
        with pytest.raises(NortPoleError):
            studio.publish(PACK, user=u, db_session=s)  # the same version again
        studio.save_draft(PACK, studio.Draft(manifest=_draft("1.1.0")), _=None)
        assert studio.publish(PACK, user=u, db_session=s).version == "1.1.0", "a new version is signed with the same key"
        n = s.execute(text("select count(*) from evolvxsi_audit_event where action='pack.install' and actor_email=:e"), {"e": u.email}).scalar()
        assert n >= 2


def test_a_pack_id_published_by_another_signer_cannot_be_taken_over(admin) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        s.add(NortPolePackVersion(pack_id=PACK, version="9.0.0", manifest=_draft("9.0.0"), digest="x" * 64, signature="x",
                                  signer_key_id=f"outside-{TAG}", active=False))
        s.commit()
        studio.save_draft(PACK, studio.Draft(manifest=_draft("9.1.0")), _=None)
        with pytest.raises(NortPoleError) as err:
            studio.publish(PACK, user=s.get(User, admin), db_session=s)
        assert "another signer" in err.value.detail


def test_a_revoked_studio_signer_stops_publishing(admin) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u = s.get(User, admin)
        studio.save_draft(PACK, studio.Draft(manifest=_draft("2.0.0")), _=None)
        studio.publish(PACK, user=u, db_session=s)
        s.get(NortPolePackSigner, studio.KEY_ID).revoked = True
        s.commit()
        studio.save_draft(PACK, studio.Draft(manifest=_draft("2.1.0")), _=None)
        with pytest.raises(NortPoleError):
            studio.publish(PACK, user=u, db_session=s)
