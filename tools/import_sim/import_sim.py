#!/usr/bin/env python3
"""Draft NortPole integration definitions from Sim's tools (Apache-2.0, see integrations/NOTICE).

Runs `extract.cjs` (which parses Sim's TypeScript with the TypeScript compiler; nothing from Sim is imported or run),
turns what it can carry into NortPole definitions and keeps only the actions that pass the NortPole format check.
Every draft names the Sim files it follows. Run it with the core virtualenv's Python so the format check is the real one:

    python tools/import_sim/import_sim.py --typescript /path/to/typescript/lib/typescript.js \\
        --sim /path/to/sim/apps/sim --out integrations/horizontal --service dropbox --service box

A service with nothing carried over writes no file. Drafts are for review; nothing here approves or installs anything.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "services" / "core"))

from nortpole.work.integrations.manifest import Integration  # noqa: E402

CATEGORY_FOR_SIM_TYPE = {
    "AI": "product", "Analytics": "product", "Commerce": "sales", "Communication": "product", "Databases": "engineering",
    "DevOps": "engineering", "Documents": "product", "Email": "product", "HR": "product", "Marketing": "gtm",
    "Observability": "engineering", "Productivity": "product", "Sales": "sales", "Search": "product",
    "Security": "engineering", "Support": "gtm",
}


def clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def action_dict(t: dict) -> dict:
    params = {}
    for name, p in t["params"].items():
        d = {"type": p["type"], "description": clip(p["description"], 300)}
        if p["required"]:
            d["required"] = True
        if p["fill"] != "user_or_model":
            d["fill"] = p["fill"]
        if "default" in p and not p["required"]:
            d["default"] = p["default"]
        params[name] = d
    request: dict = {"method": t["method"], "url": t["url"]}
    if t["query"]:
        request["query"] = t["query"]
    if t["headers"]:
        request["headers"] = t["headers"]
    if t["body"] is not None:
        request["body"] = t["body"]
    return {
        "id": t["id"][:41], "name": clip(t["name"], 80), "description": clip(t["description"], 300), "effect": t["effect"],
        **({"params": params} if params else {}), "request": request,
        "response": {"outputs": {k: {"path": o["path"], "type": o["type"], "description": clip(o["description"], 300)} for k, o in t["outputs"].items()}},
    }


def build(service: str, info: dict, tools: list[dict]) -> dict:
    block = info.get("block") or {}
    name = block.get("name") or service.replace("_", " ").title()
    name = name.replace(" (Legacy)", "")
    oauth = any(t["credential"] == "oauth" for t in tools)
    api_key = any(t["credential"] == "api_key" for t in tools)
    if oauth and api_key:
        raise ValueError("mixes OAuth and API key")
    auth = {"mode": "oauth", "provider": next(t["provider"] for t in tools if t["provider"]), "scopes": []} if oauth else {"mode": "api_key", "provider": service.replace("_", "-")} if api_key else {"mode": "none"}
    writes = any(t["effect"] == "write" for t in tools)
    return {
        "schema_version": 1, "id": service.replace("_", "-"), "name": clip(name, 80), "version": "1.0.0",
        "description": clip(block.get("description") or f"Use {name} from NortPole.", 300),
        "kind": "plugin", "group": "horizontal", "category": CATEGORY_FOR_SIM_TYPE.get(block.get("type") or "", "product"),
        "auth": auth, "hosts": sorted({t["host"] for t in tools}), "data_classes": ["internal"],
        "policy_default": "needs_approval" if (oauth or api_key or writes) else "allowed",
        "actions": [action_dict(t) for t in tools],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--typescript", required=True, help="path to typescript/lib/typescript.js (TypeScript 5)")
    ap.add_argument("--sim", required=True, type=Path, help="Sim's apps/sim folder")
    ap.add_argument("--out", required=True, type=Path, help="e.g. integrations/horizontal; files go to <out>/<category>/<service>/")
    ap.add_argument("--service", action="append", required=True)
    ap.add_argument("--report", type=Path, help="write the carried/skipped list here as JSON")
    args = ap.parse_args()
    raw = subprocess.run(["node", str(HERE / "extract.cjs"), args.typescript, str(args.sim), *args.service], check=True, capture_output=True, text=True).stdout
    data = json.loads(raw)
    report = {}
    for service, info in data.items():
        if "error" in info:
            print(f"{service}: {info['error']}")
            continue
        kept, skipped = [], [(s["file"], s["why"]) for s in info["skipped"]]
        for t in info["tools"]:
            try:  # Each action must stand on its own in the format check.
                Integration.model_validate(build(service, info, [t]))
                kept.append(t)
            except Exception as e:  # noqa: BLE001 - the reason is shown, not hidden
                skipped.append((t["file"], "format check: " + str(e).splitlines()[-2 if len(str(e).splitlines()) > 1 else -1].strip()[:140]))
        seen, unique = set(), []
        for t in kept:
            (skipped.append((t["file"], "duplicate action id")) if t["id"] in seen else unique.append(t))
            seen.add(t["id"])
        report[service] = {"carried": [t["id"] for t in unique], "skipped": skipped}
        print(f"{service}: {len(unique)} carried over, {len(skipped)} need a manual port")
        if not unique:
            continue
        draft = build(service, info, unique)
        Integration.model_validate(draft)
        dest = args.out / draft["category"] / service.replace("_", "-")
        dest.mkdir(parents=True, exist_ok=True)
        files = ", ".join(sorted({t["file"] for t in unique}))
        header = (f"# {draft['name']}: {len(unique)} actions. Adapted from Sim's tools/{service}/ (Apache-2.0, see ../../../NOTICE).\n"
                  f"# Source files: {files}. Drafted by tools/import_sim; reviewed before use. Sign-in scopes are not set yet.\n")
        (dest / "integration.yaml").write_text(header + yaml.safe_dump(draft, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
    if args.report:
        args.report.write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
