"""Validate, build and sign EvolvXSI workflow packs from source (decision 0006, phase 4).

The SDK does not import the server. It validates against the generated JSON Schema in packages/contracts, checks the
repository's folder rules, and signs the same canonical bytes the server verifies (sorted keys, no whitespace,
Ed25519). The server still runs its full checks on install.
"""

from evolvxsi_pack_sdk.core import PackError
from evolvxsi_pack_sdk.core import build
from evolvxsi_pack_sdk.core import canonical_bytes
from evolvxsi_pack_sdk.core import digest
from evolvxsi_pack_sdk.core import keygen
from evolvxsi_pack_sdk.core import load_source
from evolvxsi_pack_sdk.core import sign
from evolvxsi_pack_sdk.core import validate

__all__ = ["PackError", "build", "canonical_bytes", "digest", "keygen", "load_source", "sign", "validate"]
