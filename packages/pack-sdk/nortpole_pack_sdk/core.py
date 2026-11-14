"""Pack SDK functions. See the package docstring and README for the rules they apply."""

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

MANIFEST_FILE = "manifest.yaml"
# packages/pack-sdk/nortpole_pack_sdk/core.py -> packages/contracts/schemas/pack-manifest.schema.json
DEFAULT_SCHEMA = Path(__file__).resolve().parents[2] / "contracts" / "schemas" / "pack-manifest.schema.json"


class PackError(ValueError):
    """A pack source that cannot be validated, built or signed. The message says what to fix."""


def load_source(pack_dir: Path) -> dict[str, Any]:
    path = Path(pack_dir) / MANIFEST_FILE
    if not path.is_file():
        raise PackError(f"{path} not found: a pack folder holds a {MANIFEST_FILE}")
    try:
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise PackError(f"{path} is not valid YAML: {e}") from e
    if not isinstance(manifest, dict):
        raise PackError(f"{path} must hold a mapping at the top level")
    return manifest


def _folder_rules(pack_dir: Path, manifest: dict[str, Any]) -> list[str]:
    """Rules for packs kept in a packs/ tree: horizontal/<id> or vertical/<industry>/<id>. Other folders are not checked."""
    problems = []
    parts = Path(pack_dir).resolve().parts
    if manifest.get("id") != parts[-1]:
        problems.append(f"the folder name {parts[-1]!r} must equal the pack id {manifest.get('id')!r}")
    if len(parts) >= 3 and parts[-3] == "packs" and parts[-2] == "horizontal":
        if manifest.get("vertical") != "general":
            problems.append("a horizontal pack must have vertical: general")
    elif len(parts) >= 4 and parts[-4] == "packs" and parts[-3] == "vertical":
        if manifest.get("vertical") != parts[-2]:
            problems.append(f"a pack in vertical/{parts[-2]}/ must have vertical: {parts[-2]}")
    return problems


def validate(pack_dir: Path, schema_path: Path = DEFAULT_SCHEMA) -> dict[str, Any]:
    """Return the manifest if it passes the schema and the folder rules; raise PackError listing every problem."""
    manifest = load_source(pack_dir)
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    problems = [
        f"{'/'.join(str(p) for p in err.absolute_path) or '(top level)'}: {err.message}"
        for err in sorted(jsonschema.Draft202012Validator(schema).iter_errors(manifest), key=lambda e: list(e.absolute_path))
    ]
    problems += _folder_rules(Path(pack_dir), manifest)
    if problems:
        raise PackError("; ".join(problems))
    return manifest


def canonical_bytes(manifest: dict[str, Any]) -> bytes:
    """The exact bytes the server signs and hashes: sorted keys, no whitespace, UTF-8."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def build(pack_dir: Path, out_dir: Path, schema_path: Path = DEFAULT_SCHEMA) -> Path:
    """Validate and write <id>-<version>.json (the unsigned manifest) to out_dir."""
    manifest = validate(pack_dir, schema_path)
    out = Path(out_dir) / f"{manifest['id']}-{manifest['version']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def keygen(key_id: str) -> dict[str, str]:
    """A new Ed25519 key pair. Register the public key in the admin console; keep the private key out of the repository."""
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {
        "key_id": key_id,
        "public_key": base64.b64encode(public).decode(),
        "private_key": base64.b64encode(private).decode(),
    }


def sign(manifest: dict[str, Any], private_key_b64: str, key_id: str) -> dict[str, Any]:
    """The signed package the admin console installs: {"manifest", "signature", "key_id"}."""
    try:
        key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64, validate=True))
    except ValueError as e:
        raise PackError("the private key must be 32 bytes of Ed25519 key, base64-encoded") from e
    signature = base64.b64encode(key.sign(canonical_bytes(manifest))).decode()
    return {"manifest": manifest, "signature": signature, "key_id": key_id}
