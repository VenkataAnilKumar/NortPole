"""The bill of materials: what it lists from each lock file, what it leaves out, and that it is repeatable."""

import base64
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "sbom"
_spec = importlib.util.spec_from_file_location("generate_sbom", HERE / "generate_sbom.py")
sb = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(sb)  # type: ignore[union-attr]

SHA = "ab" * 32
UV = f'''
version = 1

[[package]]
name = "evolvxsi"
version = "0.0.0"
source = {{ virtual = "." }}
dependencies = [
    {{ name = "Requests_Lib" }},
]

[[package]]
name = "Requests_Lib"
version = "2.0.1"
source = {{ registry = "https://pypi.org/simple" }}
dependencies = [
    {{ name = "idna" }},
    {{ name = "missing-from-lock" }},
]
sdist = {{ url = "https://example.org/r.tar.gz", hash = "sha256:{SHA}", size = 1 }}

[[package]]
name = "idna"
version = "3.1"
source = {{ registry = "https://pypi.org/simple" }}
wheels = [
    {{ url = "https://example.org/idna.whl", hash = "sha256:{'cd' * 32}", size = 1 }},
]

[[package]]
name = "idna"
version = "2.0"
source = {{ registry = "https://pypi.org/simple" }}
'''

DIGEST = hashlib.sha512(b"x").digest()
INTEGRITY = "sha512-" + base64.b64encode(DIGEST).decode()
BUN = f'''{{
  "lockfileVersion": 1,
  "workspaces": {{}},
  "packages": {{
    "@scope/pkg": ["@scope/pkg@1.2.3", "", {{"dependencies": {{"left-pad": "^1"}}}}, "{INTEGRITY}"],
    "left-pad": ["left-pad@1.3.0", "", {{}}, "{INTEGRITY}"],
    "other/left-pad": ["left-pad@1.3.0", "", {{}}, "{INTEGRITY}"],
    "@evolvxsi-ai/opal": ["@evolvxsi-ai/opal@workspace:lib/opal"],
    "bad": ["bad@0.1.0", "", {{}}, "sha512-not*base64"],
    "xlsx": ["xlsx@https://cdn.example.com/xlsx-0.20.3/xlsx-0.20.3.tgz", "", {{}}, "{INTEGRITY}"],
  }},
}}
'''


def test_python_lock_lists_dependencies_but_not_the_product_itself() -> None:
    comps, deps = sb.python_components(UV)
    refs = {c["bom-ref"] for c in comps}
    assert refs == {"pkg:pypi/requests-lib@2.0.1", "pkg:pypi/idna@3.1", "pkg:pypi/idna@2.0"}, "names are normalised; the product is not a component"
    by = {c["bom-ref"]: c for c in comps}
    assert by["pkg:pypi/requests-lib@2.0.1"]["hashes"] == [{"alg": "SHA-256", "content": SHA}]
    assert "hashes" not in by["pkg:pypi/idna@3.1"], "a wheel-only package carries no hash: the SHA-256 is of the source distribution"
    # Both versions of a name are listed as possible dependencies; a name the lock does not contain is left out.
    assert deps["pkg:pypi/requests-lib@2.0.1"] == ["pkg:pypi/idna@2.0", "pkg:pypi/idna@3.1"]


def test_web_lock_lists_each_version_once_and_skips_local_packages() -> None:
    comps = sb.npm_components(BUN)
    refs = [c["bom-ref"] for c in comps]
    assert sorted(refs) == ["pkg:npm/%40scope/pkg@1.2.3", "pkg:npm/bad@0.1.0", "pkg:npm/left-pad@1.3.0",
                            "pkg:npm/xlsx@0.20.3?download_url=https%3A%2F%2Fcdn.example.com%2Fxlsx-0.20.3%2Fxlsx-0.20.3.tgz"], "scoped names are encoded, duplicates merged, workspace packages skipped, a download address kept as a qualifier"
    by = {c["bom-ref"]: c for c in comps}
    assert by["pkg:npm/left-pad@1.3.0"]["hashes"] == [{"alg": "SHA-512", "content": DIGEST.hex()}]
    assert "hashes" not in by["pkg:npm/bad@0.1.0"], "an unreadable integrity value is left out, not guessed"


def test_the_document_is_valid_in_shape_and_the_same_every_time() -> None:
    kw = dict(version="1.0.0", commit="c0ffee", timestamp="2026-11-13T00:00:00+00:00")
    a, b = sb.build(UV, BUN, **kw), sb.build(UV, BUN, **kw)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["bomFormat"] == "CycloneDX" and a["specVersion"] == "1.5" and a["serialNumber"].startswith("urn:uuid:")
    refs = {c["bom-ref"] for c in a["components"]} | {a["metadata"]["component"]["bom-ref"]}
    assert len(refs) == len(a["components"]) + 1, "references are unique"
    assert all(r in refs for d in a["dependencies"] for r in d["dependsOn"]), "no dependency points at a missing component"
    assert [c["bom-ref"] for c in a["components"]] == sorted(c["bom-ref"] for c in a["components"])
    other = sb.build(UV, BUN, version="1.0.0", commit="deadbeef", timestamp=kw["timestamp"])
    assert other["serialNumber"] != a["serialNumber"], "a different commit has a different serial number"


def test_the_real_lock_files_produce_a_consistent_document() -> None:
    root = Path(__file__).resolve().parents[2]
    bom = sb.build((root / "services/core/uv.lock").read_text(), (root / "apps/workspace/bun.lock").read_text(),
                   version="t", commit="t", timestamp="2026-01-01T00:00:00+00:00")
    assert len(bom["components"]) > 1000
    refs = {c["bom-ref"] for c in bom["components"]} | {bom["metadata"]["component"]["bom-ref"]}
    assert len(refs) == len(bom["components"]) + 1
    assert all(r in refs for d in bom["dependencies"] for r in d["dependsOn"])


def test_a_package_from_an_address_gets_a_real_version_and_a_distribution_link() -> None:
    by = {c["name"]: c for c in sb.npm_components(BUN)}
    x = by["xlsx"]
    assert x["version"] == "0.20.3"
    assert x["externalReferences"] == [{"type": "distribution", "url": "https://cdn.example.com/xlsx-0.20.3/xlsx-0.20.3.tgz"}]
