"""Pack SDK tests. Standalone: they need PyYAML, jsonschema and cryptography, not the server."""

import base64
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SDK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SDK_ROOT))

from evolvxsi_pack_sdk import PackError, build, canonical_bytes, digest, keygen, sign, validate  # noqa: E402
from evolvxsi_pack_sdk.__main__ import main  # noqa: E402

REPO = SDK_ROOT.parents[1]
HORIZONTAL = REPO / "packs" / "horizontal" / "everyday-brief"
VERTICAL = REPO / "packs" / "vertical" / "finance" / "finance-policy-review"


def _copy(src: Path, tmp: Path, *parts: str) -> Path:
    dest = tmp.joinpath("packs", *parts)
    shutil.copytree(src, dest)
    return dest


def _edit(pack: Path, **changes) -> None:  # type: ignore[no-untyped-def]
    path = pack / "manifest.yaml"
    data = yaml.safe_load(path.read_text())
    data.update(changes)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_the_repository_packs_validate() -> None:
    assert validate(HORIZONTAL)["id"] == "everyday-brief"
    assert validate(VERTICAL)["vertical"] == "finance"


def test_schema_problems_are_all_reported(tmp_path: Path) -> None:
    pack = _copy(HORIZONTAL, tmp_path, "horizontal", "everyday-brief")
    _edit(pack, templates=[], autonomy="do_anything")
    with pytest.raises(PackError) as err:
        validate(pack)
    assert "templates" in str(err.value) and "autonomy" in str(err.value)


def test_folder_rules(tmp_path: Path) -> None:
    pack = _copy(HORIZONTAL, tmp_path, "horizontal", "everyday-brief")
    _edit(pack, vertical="finance")
    with pytest.raises(PackError, match="horizontal pack must have vertical: general"):
        validate(pack)
    wrong = _copy(VERTICAL, tmp_path, "vertical", "legal", "finance-policy-review")
    with pytest.raises(PackError, match="vertical/legal/ must have vertical: legal"):
        validate(wrong)
    renamed = _copy(HORIZONTAL, tmp_path, "horizontal", "another-name")
    with pytest.raises(PackError, match="folder name"):
        validate(renamed)


def test_build_writes_the_manifest_with_the_same_digest(tmp_path: Path) -> None:
    out = build(VERTICAL, tmp_path / "dist")
    assert out.name == "finance-policy-review-1.5.0.json"
    assert digest(json.loads(out.read_text())) == digest(validate(VERTICAL))


def test_signature_verifies_over_the_canonical_bytes() -> None:
    key = keygen("ci-test")
    manifest = validate(HORIZONTAL)
    package = sign(manifest, key["private_key"], key["key_id"])
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key"]))
    public.verify(base64.b64decode(package["signature"]), canonical_bytes(package["manifest"]))
    assert canonical_bytes({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode()


def test_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(HORIZONTAL), str(VERTICAL)]) == 0
    assert main(["keygen", "cli-test"]) == 0
    key_file = tmp_path / "key.json"
    printed = capsys.readouterr().out
    key_file.write_text(printed[printed.index("{"):])  # keygen's JSON follows validate's lines
    assert main(["sign", str(VERTICAL), "--key-file", str(key_file), "--out", str(tmp_path)]) == 0
    package = json.loads((tmp_path / "finance-policy-review-1.5.0.signed.json").read_text())
    assert set(package) == {"manifest", "signature", "key_id"}
    broken = _copy(HORIZONTAL, tmp_path, "horizontal", "everyday-brief")
    _edit(broken, templates=[])
    assert main(["validate", str(broken)]) == 1
