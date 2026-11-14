#!/usr/bin/env python3
"""Search company knowledge through the NortPole search API.

    python company_search.py search "<query>" ["<query>" ...] [--source slack,google_drive] [--days 30]
                                    [--no-query-expansion]

Reads EVOLVXSI_SERVER_URL (the API base) and EVOLVXSI_PAT from the environment. Results only include
documents the current user may open. Standard library only, so it runs in any sandbox.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

_MAX_QUERIES = 3
_HTTP_TIMEOUT_SECONDS = 300


def _search_one(base: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310 - main() only accepts http(s) bases
        f"{base.rstrip('/')}/search",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        return {
            "query": body["query"],
            "error": f"HTTP {e.code}: {detail}",
            "results": None,
        }
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        return {"query": body["query"], "error": str(e), "results": None}
    results = [
        {
            "title": r.get("title"),
            "url": r.get("link"),
            "source_type": r.get("source_type"),
            "content": r.get("content"),
            "updated_at": r.get("updated_at"),
        }
        for r in payload.get("results", [])
    ]
    return {"query": body["query"], "error": None, "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="company_search.py")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="search company knowledge")
    search.add_argument(
        "queries", nargs="+", help=f"one to {_MAX_QUERIES} queries, run concurrently"
    )
    search.add_argument(
        "--source", help="comma-separated source types, e.g. slack,google_drive"
    )
    search.add_argument(
        "--days", type=int, help="only results updated in the last N days"
    )
    search.add_argument(
        "--no-query-expansion", action="store_true", help="skip query rewriting"
    )
    args = parser.parse_args(argv)

    base = os.environ.get("EVOLVXSI_SERVER_URL", "").strip()
    token = os.environ.get("EVOLVXSI_PAT", "").strip()
    if not base or not token:
        print(json.dumps({"error": "EVOLVXSI_SERVER_URL and EVOLVXSI_PAT must be set"}))
        return 2
    if not base.startswith(("http://", "https://")):
        print(json.dumps({"error": "EVOLVXSI_SERVER_URL must be an http(s) URL"}))
        return 2
    if len(args.queries) > _MAX_QUERIES:
        print(json.dumps({"error": f"at most {_MAX_QUERIES} queries per call"}))
        return 2

    common: dict[str, Any] = {"skip_query_expansion": args.no_query_expansion}
    if args.source:
        common["sources"] = [s.strip() for s in args.source.split(",") if s.strip()]
    if args.days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(args.days, 0))
        common["time_cutoff"] = cutoff.isoformat()

    bodies = [{"query": q, **common} for q in args.queries]
    with ThreadPoolExecutor(max_workers=len(bodies)) as pool:
        outcomes = list(pool.map(lambda b: _search_one(base, token, b), bodies))

    if len(outcomes) == 1:
        only = outcomes[0]
        output: dict[str, Any] = {"results": only["results"]}
        if only["error"]:
            output["error"] = only["error"]
    else:
        output = {"searches": outcomes}
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
