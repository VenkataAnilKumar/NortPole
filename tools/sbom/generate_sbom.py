#!/usr/bin/env python3
"""Write a CycloneDX 1.5 software bill of materials (JSON) from the two lock files.

  python tools/sbom/generate_sbom.py [--out sbom.cdx.json] [--version 1.2.3]

Reads services/core/uv.lock (Python) and apps/workspace/bun.lock (web). It lists what the lock files pin, not what a
particular image contains: base-image packages (the operating system, the Python and nginx images) are not included.
Python components carry the SHA-256 of the source distribution when the lock lists one (wheel-only packages carry
none) and the dependency graph the lock states. Web components carry the SHA-512 recorded by the lock; the web
dependency graph is not written. A web package fetched from an address instead of the npm registry (such as `xlsx` from a vendor's server) keeps that address as a `download_url` qualifier and a distribution link. Web packages are not marked as build-only or runtime, because the lock does not say.
The output is the same for the same lock files and commit: the timestamp is the commit's date and the serial number is
derived from the commit, so two runs can be compared. It does not state licences; tools/licenses screens those."""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import re
import subprocess
import sys
import tomllib
import uuid
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = "nortpole"


def _norm(name: str) -> str:
    """PyPI name normalisation used in package URLs."""
    return re.sub(r"[-_.]+", "-", name).lower()


def python_components(lock_text: str) -> tuple[list[dict], dict[str, list[str]]]:
    """Components and, for each, the references it depends on, from a uv lock file's text."""
    data = tomllib.loads(lock_text)
    by_name: dict[str, list[str]] = {}
    rows: list[tuple[str, dict, dict]] = []
    for p in data.get("package", []):
        src = p.get("source", {})
        if "virtual" in src or "editable" in src:  # the product itself, not a dependency
            continue
        name, version = _norm(p["name"]), p.get("version", "")
        ref = f"pkg:pypi/{name}@{version}"
        by_name.setdefault(name, []).append(ref)
        c: dict = {"type": "library", "bom-ref": ref, "name": name, "version": version, "purl": ref}
        sdist = (p.get("sdist") or {}).get("hash", "")
        if sdist.startswith("sha256:"):
            c["hashes"] = [{"alg": "SHA-256", "content": sdist.split(":", 1)[1]}]
        rows.append((ref, c, p))
    deps: dict[str, list[str]] = {}
    for ref, _, p in rows:
        deps[ref] = sorted({r for d in p.get("dependencies", []) for r in by_name.get(_norm(d["name"]), [])})
    return [c for _, c, _ in rows], deps


def _integrity_to_hash(integrity: str) -> list[dict]:
    algs = {"sha512": ("SHA-512", 128), "sha256": ("SHA-256", 64), "sha384": ("SHA-384", 96), "sha1": ("SHA-1", 40)}
    m = re.match(r"^(sha\d+)-(.+)$", integrity or "")
    if not m or m.group(1) not in algs:
        return []
    alg, hex_len = algs[m.group(1)]
    try:
        hex_value = base64.b64decode(m.group(2), validate=True).hex()
    except Exception:  # noqa: BLE001 - an unreadable value is left out rather than guessed
        return []
    return [{"alg": alg, "content": hex_value}] if len(hex_value) == hex_len else []


def npm_components(lock_text: str) -> list[dict]:
    """Components from a bun lock file's text (JSON with trailing commas)."""
    data = json.loads(re.sub(r",(\s*[}\]])", r"\1", lock_text))
    seen: dict[str, dict] = {}
    for entry in data.get("packages", {}).values():
        ident = entry[0] if entry else ""
        if "@workspace:" in ident or "@file:" in ident or "@link:" in ident:  # this repository's own packages
            continue
        name, _, version = ident.rpartition("@")
        if not name or not version:
            continue
        purl_name = quote(name, safe="/@").replace("@", "%40", 1) if name.startswith("@") else quote(name, safe="/")
        download = ""
        if re.match(r"^https?://", version):
            # Not from the npm registry (for example a tarball on a vendor's server): keep the address, take the version from the file name.
            download, m = version, re.search(r"-(\d[0-9A-Za-z.+-]*?)\.t(?:ar\.)?gz$", version)
            version = m.group(1) if m else "0"
        ref = f"pkg:npm/{purl_name}@{version}" + (f"?download_url={quote(download, safe='')}" if download else "")
        c: dict = {"type": "library", "bom-ref": ref, "name": name, "version": version, "purl": ref}
        if download:
            c["externalReferences"] = [{"type": "distribution", "url": download}]
        hashes = _integrity_to_hash(entry[3] if len(entry) > 3 else "")
        if hashes:
            c["hashes"] = hashes
        seen.setdefault(ref, c)
    return list(seen.values())


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def build(uv_lock: str, bun_lock: str, *, version: str, commit: str, timestamp: str) -> dict:
    py, py_deps = python_components(uv_lock)
    js = npm_components(bun_lock)
    components = sorted(py + js, key=lambda c: c["bom-ref"])
    root_ref = f"{PRODUCT}@{version}"
    graph = [{"ref": ref, "dependsOn": deps} for ref, deps in sorted(py_deps.items())]
    graph.insert(0, {"ref": root_ref, "dependsOn": [c["bom-ref"] for c in components]})
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"{PRODUCT}:{commit or version}")),
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "tools": {"components": [{"type": "application", "name": "nortpole-generate-sbom"}]},
            "component": {"type": "application", "bom-ref": root_ref, "name": PRODUCT, "version": version,
                          **({"properties": [{"name": "nortpole:commit", "value": commit}]} if commit else {})},
            "properties": [{"name": "nortpole:sources", "value": "services/core/uv.lock, apps/workspace/bun.lock"}],
        },
        "components": components,
        "dependencies": graph,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="sbom.cdx.json")
    ap.add_argument("--version", default=None, help="product version (default: the short commit)")
    a = ap.parse_args()
    commit = _git("rev-parse", "HEAD")
    when = _git("show", "-s", "--format=%cI", "HEAD") or datetime.datetime.now(datetime.timezone.utc).isoformat()
    uv = (ROOT / "services/core/uv.lock").read_text(encoding="utf-8")
    bun = (ROOT / "apps/workspace/bun.lock").read_text(encoding="utf-8")
    bom = build(uv, bun, version=a.version or (commit[:12] or "dev"), commit=commit, timestamp=when)
    Path(a.out).write_text(json.dumps(bom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    py = sum(1 for c in bom["components"] if c["purl"].startswith("pkg:pypi/"))
    print(f"wrote {a.out}: {py} Python and {len(bom['components']) - py} web components (commit {commit[:12] or 'unknown'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
