"""Sealing a person's integration account before it is stored.

It uses the same key and the same sealing as every other stored secret (`nortpole/utils/encryption.py`,
`ENCRYPTION_KEY_SECRET`), so there is one key to set, rotate and back up. The sealed bytes are kept as text in the
`credential` column. With no key nothing is stored, unless the deployment allows plaintext secrets for local development."""

from __future__ import annotations

import base64
import json
from typing import Any

from nortpole.utils.encryption import (
    EncryptionError,
    decrypt_bytes_to_string,
    encrypt_string_to_bytes,
    generate_key,
)

ENV = "ENCRYPTION_KEY_SECRET"

__all__ = ["ENV", "SecretsError", "generate_key", "seal", "unseal"]


class SecretsError(Exception):
    """The account could not be sealed or opened. The message never holds the account."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def seal(account: dict[str, Any]) -> str:
    try:
        return base64.b64encode(encrypt_string_to_bytes(json.dumps(account, sort_keys=True))).decode()
    except EncryptionError as exc:
        raise SecretsError(exc.code, str(exc)) from exc


def unseal(token: str) -> dict[str, Any]:
    try:
        value = json.loads(decrypt_bytes_to_string(base64.b64decode(token.encode())))
    except EncryptionError as exc:
        raise SecretsError(exc.code, str(exc)) from exc
    except ValueError as exc:
        raise SecretsError("secrets_unreadable", "The saved account can no longer be read. Connect it again.") from exc
    if not isinstance(value, dict):
        raise SecretsError("secrets_unreadable", "The saved account can no longer be read. Connect it again.")
    return value
