"""The Studio signing key is sealed before it goes into the key-value store, which keeps plain JSON."""

import base64
import json

import pytest

from nortpole.utils.encryption import ENV_KEY, generate_key
from nortpole.work.packs import studio

RAW = b"\x01" * 32


class FakeStore:
    def __init__(self) -> None:
        self.saved: dict[str, object] = {}

    def store(self, key: str, value: object) -> None:
        self.saved[key] = value


@pytest.fixture()
def key(monkeypatch: pytest.MonkeyPatch) -> str:
    k = generate_key()
    monkeypatch.setenv(ENV_KEY, k)
    return k


def test_the_stored_record_holds_no_readable_private_key(key: str) -> None:
    record = studio._sealed_record(RAW)
    text = json.dumps(record)
    assert "private_key" not in record.keys() - {"sealed_private_key"}
    assert base64.b64encode(RAW).decode() not in text
    assert studio._open_private_key(record) == RAW


def test_an_old_unsealed_record_is_read_and_sealed_in_place(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore()
    monkeypatch.setattr(studio, "get_kv_store", lambda: store)
    old = {"key_id": studio.KEY_ID, "private_key": base64.b64encode(RAW).decode()}
    assert studio._open_private_key(old) == RAW
    saved = store.saved[studio.KEY_KV]
    assert "sealed_private_key" in saved and "private_key" not in saved  # type: ignore[operator]
    assert studio._open_private_key(saved) == RAW  # type: ignore[arg-type]


def test_an_old_record_still_works_when_no_key_is_set_and_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    import nortpole.utils.encryption as encryption

    monkeypatch.delenv(ENV_KEY, raising=False)
    monkeypatch.delenv("NORTPOLE_ALLOW_PLAINTEXT_SECRETS", raising=False)
    monkeypatch.setattr(encryption, "ENCRYPTION_KEY_SECRET", "")
    store = FakeStore()
    monkeypatch.setattr(studio, "get_kv_store", lambda: store)
    old = {"key_id": studio.KEY_ID, "private_key": base64.b64encode(RAW).decode()}
    assert studio._open_private_key(old) == RAW
    assert studio.KEY_KV not in store.saved, "nothing could be sealed, so nothing was rewritten"
