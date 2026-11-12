#!/usr/bin/env python3
"""Check the licences of the installed Python packages (and optionally the web production tree).

  python tools/licenses/check_licenses.py [--python /path/to/venv/bin/python] [--web-json license-checker.json]

Exit status 1 if any package has a licence on the deny list, or one that needs review and is not in
tools/licenses/reviewed.json. This reads package metadata; it is a screen, not legal advice, and it can
miss a licence that is stated only in a file.

Web: produce the JSON with
  npx license-checker-rseidelsohn@4.4.2 --production --json --excludePrivatePackages > license-checker.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
# Licences that stop a build: strong copyleft, network copyleft, and licences that restrict use.
DENY = re.compile(r"\bAGPL|Affero|\bSSPL|Server Side Public|\bBUSL|Business Source|Commons Clause|CC-BY-NC|Non-?Commercial|\bProprietary\b|Elastic License", re.I)
# Needs a human decision recorded in reviewed.json.
REVIEW = re.compile(r"\bGPL\b|\bGNU General|LGPL|Lesser General|\bMPL|Mozilla|EPL|Eclipse|CDDL|UNKNOWN|^\s*$|\bNone\b", re.I)
PERMISSIVE = re.compile(r"\bMIT\b|Apache|\bBSD\b|\bISC\b|Python Software Foundation|\bPSF\b|Unlicense|\b0BSD\b|Zlib|CC0|Public Domain|HPND|BlueOak", re.I)


def classify(licence: str) -> str:
    """'deny', 'review' or 'ok' for one licence string (a package may state several, or an OR choice)."""
    text = licence or ""
    if DENY.search(text):
        return "deny"
    parts = re.split(r"\s+OR\s+|;", text)
    if len(parts) > 1 and any(PERMISSIVE.search(p) and not REVIEW.search(p) and not DENY.search(p) for p in parts):
        return "ok"  # dual-licensed: a permissive choice exists
    if REVIEW.search(text):
        return "review"
    return "ok" if PERMISSIVE.search(text) else "review"


def python_packages(python: str) -> list[dict]:
    code = (
        "import importlib.metadata as m, json\n"
        "out=[]\n"
        "for d in m.distributions():\n"
        "    md=d.metadata; name=md.get('Name') or ''\n"
        "    lic=md.get('License-Expression') or ''\n"
        "    if not lic:\n"
        "        l=md.get('License') or ''\n"
        "        lic=l if 0<len(l)<80 else ''\n"
        "    cls=[c.split('::')[-1].strip() for c in (md.get_all('Classifier') or []) if c.startswith('License ::')]\n"
        "    if not lic and cls: lic='; '.join(cls)\n"
        "    out.append({'name':name,'version':d.version,'license':lic})\n"
        "print(json.dumps(out))\n"
    )
    return json.loads(subprocess.run([python, "-c", code], check=True, capture_output=True, text=True).stdout)


def web_packages(path: str) -> list[dict]:
    d = json.loads(Path(path).read_text())
    return [{"name": k.rsplit("@", 1)[0], "version": k.rsplit("@", 1)[-1], "license": str(v.get("licenses"))} for k, v in d.items()]


def check(packages: list[dict], reviewed: dict[str, str]) -> tuple[list[dict], list[dict], list[dict]]:
    deny, unreviewed, accepted = [], [], []
    for p in packages:
        kind = classify(p["license"])
        key = p["name"].lower().replace("_", "-")
        if kind == "deny":
            deny.append(p)
        elif kind == "review":
            (accepted if key in reviewed else unreviewed).append(p)
    return deny, unreviewed, accepted


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--web-json")
    args = ap.parse_args()
    reviewed = {k.lower().replace("_", "-"): v for k, v in json.loads((HERE / "reviewed.json").read_text())["packages"].items()}
    packages = python_packages(args.python) + (web_packages(args.web_json) if args.web_json else [])
    deny, unreviewed, accepted = check(packages, reviewed)
    print(f"{len(packages)} packages checked; {len(accepted)} need review and have a recorded decision")
    for p in deny:
        print(f"DENIED   {p['name']} {p['version']}: {p['license']}")
    for p in unreviewed:
        print(f"REVIEW   {p['name']} {p['version']}: {p['license'] or '(no licence stated)'}  <- decide, then add to tools/licenses/reviewed.json")
    return 1 if deny or unreviewed else 0


if __name__ == "__main__":
    sys.exit(main())
