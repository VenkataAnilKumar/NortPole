#!/usr/bin/env python3
"""Write a third-party notices file: each installed Python package with its version, stated licence and the
text of the licence files shipped in the package.

  python tools/licenses/generate_notices.py [--python /path/to/venv/bin/python] --out THIRD_PARTY_NOTICES.txt

Apache-2.0 and MIT require their notices to travel with the software, so include the output in what you
distribute (for example copy it into the image). The file is large and generated, so it is not committed.
A package that ships no licence file gets a line saying so; that is a gap to look at, not a pass.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

CODE = r'''
import importlib.metadata as m, json
out = []
for d in m.distributions():
    md = d.metadata
    texts = []
    for f in (d.files or []):
        n = str(f).lower().rsplit("/", 1)[-1]
        if n.startswith(("license", "licence", "copying", "notice")) and ".dist-info" in str(f):
            try:
                texts.append((str(f).rsplit("/", 1)[-1], d.locate_file(f).read_text(encoding="utf-8", errors="replace")))
            except Exception:
                pass
    lic = md.get("License-Expression") or ""
    if not lic:
        l = md.get("License") or ""
        lic = l if 0 < len(l) < 80 else "; ".join(c.split("::")[-1].strip() for c in (md.get_all("Classifier") or []) if c.startswith("License ::"))
    out.append({"name": md.get("Name") or "", "version": d.version, "license": lic, "texts": texts})
print(json.dumps(sorted(out, key=lambda p: p["name"].lower())))
'''


def collect(python: str) -> list[dict]:
    return json.loads(subprocess.run([python, "-c", CODE], check=True, capture_output=True, text=True).stdout)


def render(packages: list[dict]) -> str:
    lines = ["THIRD-PARTY NOTICES", "", "This product includes the following third-party software.", ""]
    missing = []
    for p in packages:
        lines += ["=" * 78, f"{p['name']} {p['version']}", f"Licence stated: {p['license'] or '(none stated in package metadata)'}", ""]
        if not p["texts"]:
            missing.append(p["name"])
            lines += ["(this package ships no licence file)", ""]
        for fname, text in p["texts"]:
            lines += [f"--- {fname} ---", text.strip(), ""]
    lines += ["=" * 78, f"{len(packages)} packages; {len(missing)} ship no licence file: {', '.join(missing) or 'none'}", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    pkgs = collect(args.python)
    open(args.out, "w", encoding="utf-8").write(render(pkgs))
    print(f"wrote {args.out}: {len(pkgs)} packages, {sum(1 for p in pkgs if not p['texts'])} without a licence file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
