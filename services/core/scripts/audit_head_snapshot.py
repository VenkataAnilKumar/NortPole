"""Save the audit log's newest hash somewhere else, and later check the log against what was saved.

An audit hash chain catches an edited event and one removed from the middle. It cannot catch removal of the
newest events unless the latest hash was kept where an administrator of this machine cannot change it. Run this
from another machine (or a scheduled job whose output goes to another system):

  save:   EVOLVXSI_PASSWORD=... python audit_head_snapshot.py save  --url https://host --email admin@example.com --file heads.log
  check:  EVOLVXSI_PASSWORD=... python audit_head_snapshot.py check --url https://host --email admin@example.com --file heads.log

`save` appends one line (time, event id, hash) to the file. `check` reads the newest line of that file and asks the server
whether that event is still there, and whether the whole chain verifies. Exit status: 0 intact, 1 a problem was found,
2 it could not be compared (for example retention has since removed that event). The password is read from the
environment, never from the command line. Use an administrator account created for this job."""

from __future__ import annotations

import argparse
import datetime
import os
import sys

import requests


def _session(url: str, email: str, password: str, verify: bool | str) -> requests.Session:
    s = requests.Session()
    s.verify = verify
    r = s.post(f"{url}/api/auth/login", data={"username": email, "password": password}, timeout=30)
    if r.status_code not in (200, 204):
        sys.exit(f"sign-in failed ({r.status_code})")
    return s


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["save", "check"])
    p.add_argument("--url", required=True, help="the product address, for example https://evolvxsi.example.com")
    p.add_argument("--email", required=True)
    p.add_argument("--file", required=True, help="where heads are kept (save appends, check reads the last line)")
    p.add_argument("--ca", default=None, help="a CA certificate file to trust (for a private or self-signed certificate)")
    a = p.parse_args()
    password = os.environ.get("EVOLVXSI_PASSWORD")
    if not password:
        sys.exit("set EVOLVXSI_PASSWORD in the environment")
    url = a.url.rstrip("/")
    s = _session(url, a.email, password, a.ca or True)

    if a.mode == "save":
        h = s.get(f"{url}/api/admin/audit/head", timeout=30).json()
        if not h.get("reference"):
            print("the log has no hashed events yet; nothing saved")
            return 2
        line = f"{datetime.datetime.now(datetime.timezone.utc).isoformat()} {h['reference']}"
        with open(a.file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(f"saved {h['reference']} ({h['hashed_rows']} hashed events)")
        return 0

    try:
        with open(a.file, encoding="utf-8") as f:
            last = [ln.split() for ln in f.read().splitlines() if ln.strip()][-1]
    except (OSError, IndexError):
        sys.exit("no saved head in the file; run save first")
    reference = last[-1]
    r = s.get(f"{url}/api/admin/audit/verify", params={"anchor": reference}, timeout=300)
    if r.status_code != 200:
        sys.exit(f"the check failed ({r.status_code})")
    out = r.json()
    anchor = out.get("anchor_check", {})
    print(f"chain: {'intact' if out['ok'] else 'BROKEN'} over {out['checked']} events")
    print(f"saved head {reference}: {anchor.get('message', 'no answer')}")
    if not out["ok"] or anchor.get("ok") is False:
        return 1
    return 0 if anchor.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
