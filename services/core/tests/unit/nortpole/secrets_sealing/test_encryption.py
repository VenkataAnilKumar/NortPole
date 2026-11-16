"""Stored secrets are sealed: the inherited encrypted column types now really encrypt, and a deployment with no key
refuses to store anything unless plaintext is allowed on purpose (local development and tests)."""

import pytest

from nortpole.utils import encryption
from nortpole.utils.encryption import (
    ENV_ALLOW_PLAINTEXT,
    ENV_KEY,
    EncryptionError,
    check_configuration,
    decrypt_bytes_to_string,
    encrypt_string_to_bytes,
    generate_key,
    is_sealed,
)

SECRET = "tok-SECRET-123"


@pytest.fixture()
def key(monkeypatch: pytest.MonkeyPatch) -> str:
    k = generate_key()
    monkeypatch.setenv(ENV_KEY, k)
    return k


@pytest.fixture()
def no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_KEY, raising=False)
    monkeypatch.setattr(encryption, "ENCRYPTION_KEY_SECRET", "")


def test_a_secret_is_sealed_and_opens_again(key: str) -> None:
    sealed = encrypt_string_to_bytes(SECRET)
    assert is_sealed(sealed) and SECRET.encode() not in sealed
    assert decrypt_bytes_to_string(sealed) == SECRET


def test_sealing_the_same_secret_twice_gives_different_bytes(key: str) -> None:
    assert encrypt_string_to_bytes(SECRET) != encrypt_string_to_bytes(SECRET)


def test_a_passphrase_works_as_well_as_a_generated_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_KEY, "a long passphrase that someone chose")
    sealed = encrypt_string_to_bytes(SECRET)
    assert SECRET.encode() not in sealed and decrypt_bytes_to_string(sealed) == SECRET
    monkeypatch.setenv(ENV_KEY, "a different passphrase")
    with pytest.raises(EncryptionError):
        decrypt_bytes_to_string(sealed)


def test_with_no_key_a_secret_is_refused(no_key: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_ALLOW_PLAINTEXT, raising=False)
    with pytest.raises(EncryptionError) as err:
        encrypt_string_to_bytes(SECRET)
    assert err.value.code == "secrets_key_missing" and SECRET not in str(err.value)


def test_plaintext_is_allowed_only_when_asked_for(no_key: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_ALLOW_PLAINTEXT, "true")
    stored = encrypt_string_to_bytes(SECRET)
    assert stored == SECRET.encode() and not is_sealed(stored)
    assert decrypt_bytes_to_string(stored) == SECRET


def test_a_value_stored_before_sealing_still_reads_and_a_sealed_one_needs_the_key(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    assert decrypt_bytes_to_string(SECRET.encode()) == SECRET, "an upgrade must not lock anyone out"
    sealed = encrypt_string_to_bytes(SECRET)
    monkeypatch.delenv(ENV_KEY)
    monkeypatch.setattr(encryption, "ENCRYPTION_KEY_SECRET", "")
    with pytest.raises(EncryptionError) as err:
        decrypt_bytes_to_string(sealed)
    assert err.value.code == "secrets_key_missing"


def test_an_explicit_key_opens_only_what_that_key_sealed(key: str) -> None:
    other = generate_key()
    sealed = encrypt_string_to_bytes(SECRET, key=other)
    assert decrypt_bytes_to_string(sealed, key=other) == SECRET
    with pytest.raises(EncryptionError):
        decrypt_bytes_to_string(sealed, key=key)
    with pytest.raises(EncryptionError):
        decrypt_bytes_to_string(SECRET.encode(), key=key)  # plain text is not "sealed with this key"


def test_tampered_bytes_are_refused(key: str) -> None:
    sealed = bytearray(encrypt_string_to_bytes(SECRET))
    sealed[-3] ^= 0x01
    with pytest.raises(EncryptionError):
        decrypt_bytes_to_string(bytes(sealed))


def test_the_error_never_holds_the_secret(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    sealed = encrypt_string_to_bytes(SECRET)
    monkeypatch.setenv(ENV_KEY, generate_key())
    with pytest.raises(EncryptionError) as err:
        decrypt_bytes_to_string(sealed)
    assert SECRET not in str(err.value) and SECRET not in repr(err.value)


def test_startup_refuses_to_run_without_a_key_unless_plaintext_is_allowed(no_key: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_ALLOW_PLAINTEXT, raising=False)
    with pytest.raises(RuntimeError, match=ENV_KEY):
        check_configuration()
    monkeypatch.setenv(ENV_ALLOW_PLAINTEXT, "true")
    check_configuration()


def test_startup_passes_with_a_key(key: str) -> None:
    check_configuration()
