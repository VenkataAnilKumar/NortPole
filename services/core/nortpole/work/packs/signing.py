"""Ed25519 signatures over the canonical manifest. Only keys an administrator
registered as trusted, and has not revoked, can activate a pack."""

from __future__ import annotations

import base64
import binascii

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class SignatureProblem(Exception):
    """Carries a reason safe to show: which check failed."""


def parse_public_key(b64: str) -> Ed25519PublicKey:
    try:
        raw = base64.b64decode(b64, validate=True)
        if len(raw) != 32:
            raise ValueError
        return Ed25519PublicKey.from_public_bytes(raw)
    except (binascii.Error, ValueError) as e:
        raise SignatureProblem("The signer key is not a valid Ed25519 public key (32 bytes, base64).") from e


def verify(public_key_b64: str, signature_b64: str, message: bytes) -> None:
    key = parse_public_key(public_key_b64)
    try:
        sig = base64.b64decode(signature_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise SignatureProblem("The signature is not valid base64.") from e
    try:
        key.verify(sig, message)
    except InvalidSignature as e:
        raise SignatureProblem("The signature does not match the manifest: it was changed or signed by another key.") from e
