"""An integration account is sealed with the shared key (nortpole/utils/encryption.py) before it is stored."""

import pytest

from nortpole.work.integrations import secrets
from nortpole.work.integrations.secrets import SecretsError

ACCOUNT = {"access_token": "tok-SECRET-1", "refresh_token": "ref-SECRET-2"}


@pytest.fixture()
def key(monkeypatch: pytest.MonkeyPatch) -> str:
    k = secrets.generate_key()
    monkeypatch.setenv(secrets.ENV, k)
    return k


def test_a_sealed_account_holds_nothing_readable_and_opens_again(key: str) -> None:
    sealed = secrets.seal(ACCOUNT)
    assert "SECRET" not in sealed and "access_token" not in sealed
    assert secrets.unseal(sealed) == ACCOUNT


def test_sealing_the_same_account_twice_gives_different_text(key: str) -> None:
    assert secrets.seal(ACCOUNT) != secrets.seal(ACCOUNT)


def test_with_no_key_nothing_is_sealed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(secrets.ENV, raising=False)
    monkeypatch.delenv("NORTPOLE_ALLOW_PLAINTEXT_SECRETS", raising=False)
    import nortpole.utils.encryption as encryption

    monkeypatch.setattr(encryption, "ENCRYPTION_KEY_SECRET", "")
    with pytest.raises(SecretsError) as err:
        secrets.seal(ACCOUNT)
    assert err.value.code == "secrets_key_missing" and "tok-SECRET-1" not in str(err.value)


def test_a_changed_key_cannot_open_an_old_account_and_the_error_is_safe(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    sealed = secrets.seal(ACCOUNT)
    monkeypatch.setenv(secrets.ENV, secrets.generate_key())
    with pytest.raises(SecretsError) as err:
        secrets.unseal(sealed)
    assert err.value.code == "secrets_unreadable" and "tok-SECRET-1" not in str(err.value)


def test_tampered_text_is_refused(key: str) -> None:
    sealed = secrets.seal(ACCOUNT)
    with pytest.raises(SecretsError):
        secrets.unseal(sealed[:-6] + ("AAAAAA" if not sealed.endswith("AAAAAA") else "BBBBBB"))
