"""Sealing a person's integration account before it is stored.

The inherited "encrypted" column types are not encrypted in this edition (their encrypt function returns the text
unchanged), so integration accounts are sealed here with Fernet (AES-128-CBC with an HMAC) before they reach the
database, and unsealed only for the moment of a call.

The key is `NORTPOLE_SECRETS_KEY`: one 32-byte url-safe base64 key, or several separated by commas, newest first. The
first key seals; any key unseals, so a key can be rotated by adding a new one in front and re-saving accounts later.
With no key nothing is stored: a deployment that forgot to set one fails closed instead of keeping accounts readable."""

from __future__ import annotations

import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

ENV = "NORTPOLE_SECRETS_KEY"


class SecretsError(Exception):
    """The account could not be sealed or opened. The message never holds the account."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fernet() -> MultiFernet:
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        raise SecretsError("secrets_key_missing", f"{ENV} is not set, so accounts cannot be stored. An administrator must set it.")
    try:
        return MultiFernet([Fernet(part.strip().encode()) for part in raw.split(",") if part.strip()])
    except (ValueError, TypeError) as exc:
        raise SecretsError("secrets_key_invalid", f"{ENV} is not a valid key. Generate one with Fernet.generate_key().") from exc


def generate_key() -> str:
    return Fernet.generate_key().decode()


def seal(account: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(account, sort_keys=True).encode()).decode()


def unseal(token: str) -> dict[str, Any]:
    try:
        value = json.loads(_fernet().decrypt(token.encode()).decode())
    except InvalidToken as exc:
        raise SecretsError("secrets_unreadable", "The saved account can no longer be read (the key changed). Connect it again.") from exc
    if not isinstance(value, dict):
        raise SecretsError("secrets_unreadable", "The saved account can no longer be read. Connect it again.")
    return value
