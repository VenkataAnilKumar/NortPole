import base64
import os
from typing import Any
from urllib.parse import urlparse, urlunparse

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from nortpole.configs.app_configs import ENCRYPTION_KEY_SECRET
from nortpole.configs.constants import MASK_CREDENTIAL_LONG_RE, MASK_CREDENTIAL_SHORT
from nortpole.connectors.google_utils.shared_constants import (
    DB_CREDENTIALS_AUTHENTICATION_METHOD,
)
from nortpole.utils.logger import setup_logger
from nortpole.utils.variable_functionality import fetch_versioned_implementation

logger = setup_logger()


SEALED_PREFIX = b"np1:"
ENV_KEY = "ENCRYPTION_KEY_SECRET"
ENV_ALLOW_PLAINTEXT = "NORTPOLE_ALLOW_PLAINTEXT_SECRETS"
_warned_plaintext = False


class EncryptionError(Exception):
    """A secret could not be sealed or opened. `code` is stable; the message never holds the secret."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def plaintext_allowed() -> bool:
    return os.environ.get(ENV_ALLOW_PLAINTEXT, "").strip().lower() in ("1", "true", "yes")


def current_key() -> str:
    # Read at call time so a key set after import (a test, a rotation run) is honoured.
    return (os.environ.get(ENV_KEY) or ENCRYPTION_KEY_SECRET or "").strip()


def _fernet(key: str | None) -> Fernet | None:
    """The sealing key for `key` (or the configured one); None when there is none.

    A 32-byte url-safe base64 key (what `Fernet.generate_key()` prints) is used as it is; any other text is treated as a
    passphrase and stretched with HKDF-SHA256, so an operator can use either."""
    material = (key if key is not None else current_key()).strip()
    if not material:
        return None
    try:
        return Fernet(material.encode())
    except (ValueError, TypeError):
        derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"nortpole-secrets-v1").derive(material.encode())
        return Fernet(base64.urlsafe_b64encode(derived))


def generate_key() -> str:
    return Fernet.generate_key().decode()


def is_sealed(data: bytes) -> bool:
    return data.startswith(SEALED_PREFIX)


# IMPORTANT DO NOT DELETE, THIS IS USED BY fetch_versioned_implementation
def _encrypt_string(input_str: str, key: str | None = None) -> bytes:
    """Seal a secret. With no key the secret is refused, unless the deployment says plaintext is acceptable
    (`NORTPOLE_ALLOW_PLAINTEXT_SECRETS=true`, for local development and tests), in which case it is stored as before."""
    global _warned_plaintext
    fernet = _fernet(key)
    if fernet is None:
        if not plaintext_allowed():
            raise EncryptionError(
                "secrets_key_missing",
                f"{ENV_KEY} is not set, so secrets cannot be stored. Set it (python -c 'from cryptography.fernet import Fernet; "
                f"print(Fernet.generate_key().decode())') or, for local development only, set {ENV_ALLOW_PLAINTEXT}=true.",
            )
        if not _warned_plaintext:
            logger.warning("%s is not set: secrets are being stored UNENCRYPTED (%s=true).", ENV_KEY, ENV_ALLOW_PLAINTEXT)
            _warned_plaintext = True
        return input_str.encode()
    return SEALED_PREFIX + fernet.encrypt(input_str.encode())


# IMPORTANT DO NOT DELETE, THIS IS USED BY fetch_versioned_implementation
def _decrypt_bytes(input_bytes: bytes, key: str | None = None) -> str:
    """Open a sealed secret. A value stored before sealing existed (no prefix) is still read as plain text, so an upgrade
    does not lock anyone out; it is sealed by the next rotation run. With an explicit `key` only a value sealed with that
    key opens, which is how the rotation tool tells what still needs re-sealing."""
    data = bytes(input_bytes)
    if is_sealed(data):
        fernet = _fernet(key)
        if fernet is None:
            raise EncryptionError("secrets_key_missing", f"A stored secret is sealed but {ENV_KEY} is not set.")
        try:
            return fernet.decrypt(data[len(SEALED_PREFIX):]).decode()
        except InvalidToken as exc:
            raise EncryptionError("secrets_unreadable", "A stored secret cannot be opened with this key (the key changed).") from exc
    if key is not None:
        raise EncryptionError("secrets_unreadable", "The value is not sealed with this key.")
    return data.decode()


def check_configuration() -> None:
    """Run at startup: refuse to start where secrets would be stored readable by accident."""
    if not current_key():
        if plaintext_allowed():
            logger.warning("%s is not set: secrets will be stored UNENCRYPTED (%s=true). Do not use this outside development.", ENV_KEY, ENV_ALLOW_PLAINTEXT)
            return
        raise RuntimeError(
            f"{ENV_KEY} is not set. Stored secrets (connector credentials, API keys, bot tokens, integration accounts) must be "
            f"sealed. Generate a key with `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`, "
            f"set {ENV_KEY}, and keep it with your backups. For local development only, set {ENV_ALLOW_PLAINTEXT}=true."
        )
    if _decrypt_bytes(_encrypt_string("check")) != "check":
        raise RuntimeError(f"{ENV_KEY} did not pass a seal and open check.")


def mask_string(sensitive_str: str) -> str:
    """Masks a sensitive string, showing first and last few characters.
    If the string is too short to safely mask, returns a fully masked placeholder.
    """
    visible_start = 4
    visible_end = 4
    min_masked_chars = 6

    if len(sensitive_str) < visible_start + visible_end + min_masked_chars:
        return MASK_CREDENTIAL_SHORT

    return f"{sensitive_str[:visible_start]}...{sensitive_str[-visible_end:]}"


# Exact env-var keys whose values are non-sensitive and worth seeing in logs
_UNMASKED_ENV_KEYS = {
    "AWS_REGION",
    "AWS_REGION_NAME",
    "VERTEX_LOCATION",
}

# Key suffixes for provider base URLs (e.g. ANTHROPIC_BASE_URL, OLLAMA_API_BASE).
# Every provider tends to have its own <PROVIDER>_API_BASE / <PROVIDER>_BASE_URL,
# so match by suffix rather than enumerating each one.
_UNMASKED_ENV_KEY_SUFFIXES = (
    "_API_BASE",
    "_BASE_URL",
)


def _is_unmasked_env_key(key: str) -> bool:
    upper = key.upper()
    return upper in _UNMASKED_ENV_KEYS or upper.endswith(_UNMASKED_ENV_KEY_SUFFIXES)


def _sanitize_url_for_logging(value: str) -> str:
    """Return a URL with any embedded userinfo (user:pass@) stripped.

    Falls back to fully masking if credentials are present, so they never reach
    the logs even when the host itself is safe to show.
    """
    parsed = urlparse(value)
    if parsed.username or parsed.password:
        return mask_string(value)
    netloc = parsed.hostname or ""
    try:
        port: int | None = parsed.port
    except ValueError:
        return mask_string(value)
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, "", ""))


def mask_env_value_for_logging(key: str, value: str) -> str:
    """Mask env values, leaving only explicitly-allowlisted keys readable.

    Allowlisted keys (provider base URLs via the _API_BASE / _BASE_URL suffixes,
    plus a few exact keys like AWS_REGION) are logged so overrides like
    ANTHROPIC_BASE_URL or OLLAMA_API_BASE are visible; if such a value is a URL we
    still strip any embedded userinfo defensively. Every other key is masked,
    regardless of what its value looks like.
    """
    if not _is_unmasked_env_key(key):
        return mask_string(value)
    if value.lower().startswith(("http://", "https://")):
        return _sanitize_url_for_logging(value)
    return value


def is_masked_credential(value: str) -> bool:
    """Return True if the string looks like a `mask_string` placeholder.

    `mask_string` has two output formats:
    - Short strings (< 14 chars): "••••••••••••" (U+2022 BULLET)
    - Long strings (>= 14 chars): "abcd...wxyz" (first4 + "..." + last4)
    """
    # The whole placeholder, not any bullet: a real secret may contain one.
    return value == MASK_CREDENTIAL_SHORT or bool(MASK_CREDENTIAL_LONG_RE.match(value))


def reject_masked_credentials(credentials: dict[str, Any]) -> None:
    """Raise if any credential string value contains mask placeholder characters.

    Used as a defensive net at write boundaries so that masked values
    round-tripped from `mask_string` are never persisted as real credentials.

    Recurses into nested dicts and lists to stay symmetric with
    `mask_credential_dict`, which masks nested string values. The error
    message includes a dotted path like `oauth.client_secret` or
    `keys[2]` so callers can pinpoint the offending field.
    """
    _reject_masked_in_dict(credentials, path="")


def _reject_masked_in_dict(credentials: dict[str, Any], path: str) -> None:
    for key, val in credentials.items():
        field_path = f"{path}.{key}" if path else key
        _reject_masked_in_value(val, field_path)


def _reject_masked_in_value(val: Any, path: str) -> None:
    if isinstance(val, str):
        if is_masked_credential(val):
            raise ValueError(
                f"Credential field '{path}' contains masked placeholder "
                "characters. Please provide the actual credential value."
            )
        return
    if isinstance(val, dict):
        _reject_masked_in_dict(val, path=path)
        return
    if isinstance(val, list):
        for index, item in enumerate(val):
            _reject_masked_in_value(item, f"{path}[{index}]")


MASK_CREDENTIALS_WHITELIST = {
    DB_CREDENTIALS_AUTHENTICATION_METHOD,
    "wiki_base",
    "cloud_name",
    "cloud_id",
    # Where an account works (its realm): not secrets, and the add-connector
    # form compares them with the realm typed above the saved accounts.
    "github_base_url",
    "gitlab_url",
    "bookstack_base_url",
    "outline_base_url",
    "gong_base_url",
    "loopio_subdomain",
    "zendesk_subdomain",
    "base_url",
    "freshdesk_domain",
    "domain",
    "highspot_url",
    "testrail_base_url",
    # OAuth scope lists are public identifiers, not secrets, and masked list
    # items cannot round-trip through a chip editor.
    "scopes",
}


def mask_credential_dict(credential_dict: dict[str, Any]) -> dict[str, Any]:
    masked_creds: dict[str, Any] = {}
    for key, val in credential_dict.items():
        # Whitelisted keys pass through whole (e.g. authentication_method so
        # the frontend can disambiguate credential kinds) whatever their type.
        if key in MASK_CREDENTIALS_WHITELIST:
            masked_creds[key] = val
        elif isinstance(val, str):
            masked_creds[key] = mask_string(val)
        elif isinstance(val, dict):
            masked_creds[key] = mask_credential_dict(val)
        elif isinstance(val, list):
            masked_creds[key] = _mask_list(val)
        elif isinstance(val, (bool, type(None))):
            masked_creds[key] = val
        elif isinstance(val, (int, float)):
            masked_creds[key] = "*****"
        else:
            masked_creds[key] = "*****"

    return masked_creds


def _mask_list(items: list[Any]) -> list[Any]:
    masked: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            masked.append(mask_credential_dict(item))
        elif isinstance(item, str):
            masked.append(mask_string(item))
        elif isinstance(item, list):
            masked.append(_mask_list(item))
        elif isinstance(item, (bool, type(None))):
            masked.append(item)
        else:
            masked.append("*****")
    return masked


def _restore_masked_value(incoming: Any, stored: Any, masked_stored: Any) -> Any:
    if (
        isinstance(incoming, dict)
        and isinstance(stored, dict)
        and isinstance(masked_stored, dict)
    ):
        restored = dict(incoming)
        for key, value in incoming.items():
            if key not in stored or key not in masked_stored:
                continue
            restored[key] = _restore_masked_value(
                value, stored[key], masked_stored[key]
            )
        return restored

    if (
        isinstance(incoming, list)
        and isinstance(stored, list)
        and isinstance(masked_stored, list)
    ):
        restored_list = list(incoming)
        for index, value in enumerate(incoming):
            if index >= len(stored) or index >= len(masked_stored):
                continue
            restored_list[index] = _restore_masked_value(
                value,
                stored[index],
                masked_stored[index],
            )
        return restored_list

    if incoming == masked_stored:
        return stored

    return incoming


def restore_masked_credentials(
    incoming: dict[str, Any], stored: dict[str, Any]
) -> dict[str, Any]:
    """Inverse of ``mask_credential_dict`` for edit round-trips: any incoming
    value that equals the masked form of the stored value is replaced with the
    stored value, recursing through nested dicts and lists. Values the caller
    changed pass through untouched.
    """
    restored = _restore_masked_value(
        incoming,
        stored,
        mask_credential_dict(stored),
    )
    if not isinstance(restored, dict):
        return incoming
    return restored


def encrypt_string_to_bytes(intput_str: str, key: str | None = None) -> bytes:
    versioned_encryption_fn = fetch_versioned_implementation(
        "nortpole.utils.encryption", "_encrypt_string"
    )
    return versioned_encryption_fn(intput_str, key=key)


def decrypt_bytes_to_string(intput_bytes: bytes, key: str | None = None) -> str:
    versioned_decryption_fn = fetch_versioned_implementation(
        "nortpole.utils.encryption", "_decrypt_bytes"
    )
    return versioned_decryption_fn(intput_bytes, key=key)
