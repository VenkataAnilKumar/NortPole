"""The pack SDK (packages/pack-sdk) agrees with the server: same digest, a signature the server verifies, and the same
verdict on what a valid manifest is (decision 0006, phase 4)."""

import copy
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from evolvxsi.work.packs.manifest import Manifest
from evolvxsi.work.packs.manifest import digest as server_digest
from evolvxsi.work.packs.signing import verify
from evolvxsi.work.packs.manifest import canonical_bytes as server_canonical_bytes

REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO / "packages" / "pack-sdk"))

import evolvxsi_pack_sdk as sdk  # noqa: E402

PACKS = [REPO / "packs/horizontal/everyday-brief", REPO / "packs/vertical/finance/finance-policy-review"]


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.name)
def test_sdk_digest_and_signature_match_the_server(pack: Path) -> None:
    manifest = sdk.validate(pack)
    Manifest.model_validate(manifest)
    assert sdk.canonical_bytes(manifest) == server_canonical_bytes(manifest)
    assert sdk.digest(manifest) == server_digest(manifest)
    key = sdk.keygen("server-check")
    package = sdk.sign(manifest, key["private_key"], key["key_id"])
    verify(key["public_key"], package["signature"], server_canonical_bytes(package["manifest"]))


BROKEN = {
    "no templates": lambda m: m.update(templates=[]),
    "unknown autonomy": lambda m: m.update(autonomy="do_anything"),
    "bad version": lambda m: m.update(version="1.0"),
    "bad id": lambda m: m.update(id="Everyday Brief"),
    "extra field": lambda m: m.update(owner="someone"),
    "long name": lambda m: m.update(name="x" * 500),
}


@pytest.mark.parametrize("change", list(BROKEN), ids=list(BROKEN))
def test_the_sdk_schema_rejects_what_the_server_rejects(change: str, tmp_path: Path) -> None:
    import yaml

    manifest = copy.deepcopy(sdk.load_source(PACKS[0]))
    BROKEN[change](manifest)
    with pytest.raises(ValidationError):
        Manifest.model_validate(manifest)
    pack = tmp_path / "packs" / "horizontal" / "everyday-brief"
    pack.mkdir(parents=True)
    (pack / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    with pytest.raises(sdk.PackError):
        sdk.validate(pack)


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.name)
def test_a_stored_version_re_verifies_from_the_sdk_signed_bytes(pack: Path) -> None:
    """The server keeps the SDK's exact canonical bytes beside the normalized copy it reads, and those re-verify
    (digest, signature, content). everyday-brief leaves defaults out, so its normalized copy alone could not."""
    from evolvxsi.work.packs.integrity import check_version
    from evolvxsi.work.packs.models import EvolvXSIPackSigner, EvolvXSIPackVersion

    manifest = sdk.validate(pack)
    normalized = Manifest.model_validate(manifest).model_dump(mode="json")
    if pack.name == "everyday-brief":
        assert server_digest(normalized) != sdk.digest(manifest), "everyday-brief is expected to leave defaults out"
    key = sdk.keygen("re-verify")
    package = sdk.sign(manifest, key["private_key"], key["key_id"])
    row = EvolvXSIPackVersion(pack_id=manifest["id"], version=manifest["version"], manifest=normalized,
                              signed_manifest=server_canonical_bytes(package["manifest"]).decode("utf-8"),
                              digest=server_digest(package["manifest"]), signature=package["signature"], signer_key_id=key["key_id"])
    assert row.signed_manifest.encode("utf-8") == sdk.canonical_bytes(manifest)
    check = check_version(row, EvolvXSIPackSigner(key_id=key["key_id"], public_key=key["public_key"], revoked=False))
    assert check.status == "verified", check.problems
