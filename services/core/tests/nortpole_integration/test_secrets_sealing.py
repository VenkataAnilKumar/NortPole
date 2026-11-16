"""Inherited encrypted columns on the real database: sealed when a key is set, readable if stored before sealing existed,
sealed by the rotation tool, and unreadable with the wrong key."""

import uuid

import pytest
from sqlalchemy import text

from nortpole.configs.constants import DocumentSource
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import Credential
from nortpole.db.rotate_encryption_key import rotate_encryption_key
from nortpole.utils import encryption
from nortpole.utils.encryption import ENV_ALLOW_PLAINTEXT, ENV_KEY, generate_key
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]
TOKEN = f"tok-SECRET-{TAG}"


@pytest.fixture(autouse=True)
def keep_the_credential_table_as_it_was():  # type: ignore[no-untyped-def]
    """The rotation tool works on whole tables, so put every other row back exactly as it was afterwards."""
    with get_session_with_current_tenant() as s:
        before = {r[0]: bytes(r[1]) for r in s.execute(text("select id, credential_json from credential where credential_json is not null")).all()}
    yield
    with get_session_with_current_tenant() as s:
        for cid, data in before.items():
            s.execute(text("update credential set credential_json = :d where id = :i"), {"d": data, "i": cid})
        s.commit()


@pytest.fixture()
def row_id():  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        c = Credential(name=f"sealing-{TAG}", source=DocumentSource.NOT_APPLICABLE, credential_json={"api_token": TOKEN})
        s.add(c)
        s.commit()
        cid = c.id
    yield cid
    with get_session_with_current_tenant() as s:
        s.query(Credential).filter_by(id=cid).delete()
        s.commit()


def raw(cid: int) -> bytes:
    with get_session_with_current_tenant() as s:
        return bytes(s.execute(text("select credential_json from credential where id = :i"), {"i": cid}).scalar())


def read(cid: int) -> dict:
    with get_session_with_current_tenant() as s:
        return s.get(Credential, cid).credential_json.get_value(apply_mask=False)  # type: ignore[union-attr]


def use_key(monkeypatch: pytest.MonkeyPatch, key: str | None) -> None:
    if key is None:
        monkeypatch.delenv(ENV_KEY, raising=False)
        monkeypatch.setattr(encryption, "ENCRYPTION_KEY_SECRET", "")
    else:
        monkeypatch.setenv(ENV_KEY, key)


def test_with_a_key_the_stored_bytes_hold_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    use_key(monkeypatch, generate_key())
    with get_session_with_current_tenant() as s:
        c = Credential(name=f"sealed-{TAG}", source=DocumentSource.NOT_APPLICABLE, credential_json={"api_token": TOKEN})
        s.add(c)
        s.commit()
        cid = c.id
    try:
        stored = raw(cid)
        assert stored.startswith(b"np1:") and TOKEN.encode() not in stored and b"api_token" not in stored
        assert read(cid) == {"api_token": TOKEN}
        use_key(monkeypatch, generate_key())
        with pytest.raises(encryption.EncryptionError):
            read(cid)
    finally:
        with get_session_with_current_tenant() as s:
            s.query(Credential).filter_by(id=cid).delete()
            s.commit()


def test_a_value_stored_before_sealing_still_reads_and_the_rotation_tool_seals_it(row_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    # `row_id` was written in the clear: the test environment allows plaintext and sets no key.
    assert raw(row_id).startswith(b"{") and TOKEN.encode() in raw(row_id)
    use_key(monkeypatch, generate_key())
    assert read(row_id) == {"api_token": TOKEN}, "an upgrade must not lock anyone out"
    with get_session_with_current_tenant() as s:
        dry = rotate_encryption_key(s, None, dry_run=True, only_tables={"credential"})
    assert dry.get("credential.credential_json", 0) >= 1 and TOKEN.encode() in raw(row_id), "a dry run changes nothing"
    with get_session_with_current_tenant() as s:
        done = rotate_encryption_key(s, None, only_tables={"credential"})
    assert done.get("credential.credential_json", 0) >= 1
    assert raw(row_id).startswith(b"np1:") and TOKEN.encode() not in raw(row_id)
    assert read(row_id) == {"api_token": TOKEN}
    with get_session_with_current_tenant() as s:
        assert rotate_encryption_key(s, None, only_tables={"credential"}) == {}, "running it again changes nothing"


def test_the_rotation_tool_moves_sealed_values_to_a_new_key(row_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    old, new = generate_key(), generate_key()
    use_key(monkeypatch, old)
    with get_session_with_current_tenant() as s:
        rotate_encryption_key(s, None, only_tables={"credential"})
    assert raw(row_id).startswith(b"np1:")
    use_key(monkeypatch, new)
    with get_session_with_current_tenant() as s:
        rotate_encryption_key(s, old, only_tables={"credential"})
    assert read(row_id) == {"api_token": TOKEN}
    use_key(monkeypatch, old)
    with pytest.raises(encryption.EncryptionError):
        read(row_id)


def test_with_no_key_and_no_permission_nothing_is_written(monkeypatch: pytest.MonkeyPatch) -> None:
    use_key(monkeypatch, None)
    monkeypatch.delenv(ENV_ALLOW_PLAINTEXT, raising=False)
    with pytest.raises(encryption.EncryptionError) as err:
        # The column seals the value as soon as it is assigned, so the refusal comes before anything reaches the database.
        Credential(name=f"refused-{TAG}", source=DocumentSource.NOT_APPLICABLE, credential_json={"api_token": TOKEN})
    assert TOKEN not in str(err.value)
    with get_session_with_current_tenant() as s:
        assert s.query(Credential).filter_by(name=f"refused-{TAG}").count() == 0
