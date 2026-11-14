"""Sign a pack manifest. Authoring and release tool; run it where the private key lives.

  python scripts/sign_pack.py keygen  <key-id>                     prints a new Ed25519 key pair
  python scripts/sign_pack.py sign    <manifest.json> <private-key-b64> <key-id>   prints the package JSON

The package is {"manifest", "signature", "key_id"}. The signature covers the
canonical manifest bytes (sorted keys, no whitespace), the same bytes the
server hashes and verifies. Register the PUBLIC key as a trusted signer in the
admin console; never share the private key.
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from nortpole.work.packs.manifest import Manifest, canonical_bytes, digest  # noqa: E402


def keygen(key_id: str) -> None:
    k = Ed25519PrivateKey.generate()
    priv = base64.b64encode(k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())).decode()
    pub = base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    print(json.dumps({"key_id": key_id, "public_key": pub, "private_key": priv}, indent=2))


def sign(manifest_path: str, private_b64: str, key_id: str) -> None:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    Manifest.model_validate(manifest)  # refuse to sign an invalid manifest
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_b64))
    sig = base64.b64encode(key.sign(canonical_bytes(manifest))).decode()
    print(json.dumps({"manifest": manifest, "signature": sig, "key_id": key_id}, indent=2))
    print(f"digest: {digest(manifest)}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "keygen":
        keygen(sys.argv[2])
    elif len(sys.argv) == 5 and sys.argv[1] == "sign":
        sign(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
        sys.exit(2)
