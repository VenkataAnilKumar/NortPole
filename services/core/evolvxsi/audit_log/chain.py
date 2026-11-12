"""A hash chain over the audit table, so that changing or removing a row shows up.

Each new event stores prev_hash (the hash of the event before it) and row_hash = SHA-256 of prev_hash and
the event's own fields. Verification walks the chain and reports the first row whose content or link does
not match. What this does and does not give:
* it detects an edited row and a row removed from the middle;
* it does NOT detect removal of the newest rows, or a rewrite of the whole chain by someone who can
  recompute every hash, unless the latest hash was kept somewhere they cannot reach (the log line written
  with every event carries it; keep those logs off this machine);
* rows written before the chain existed are not covered.
The prune (retention) deletes the oldest rows on purpose and records the hash of the last row it removed,
so the chain from the first kept row still verifies."""

from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any

GENESIS = "0" * 64
LOCK_KEY = 7210001  # one advisory lock serialises writers of the chain


def canonical(row: Any) -> str:
    created = row.created_at.astimezone(datetime.timezone.utc).isoformat()
    return json.dumps(
        [row.id, created, row.action, row.outcome, row.actor_user_id, row.actor_email, row.resource_type, row.resource_id, row.summary, row.details],
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
    )


def link(prev_hash: str, row: Any) -> str:
    return hashlib.sha256((prev_hash + "\n" + canonical(row)).encode("utf-8")).hexdigest()


def check_rows(rows: Any, anchor: str | None) -> dict:
    """Pure: walk hashed rows in id order (any iterable) from the anchor (or genesis) and report the first break."""
    expected = anchor or GENESIS
    checked, first_break, head = 0, None, None
    for r in rows:
        if first_break is None:
            if r.prev_hash != expected:
                first_break = {"id": r.id, "reason": "a row before this one is missing or was changed (the link does not match)"}
            elif link(r.prev_hash, r) != r.row_hash:
                first_break = {"id": r.id, "reason": "this row's content no longer matches its hash"}
        expected, head = r.row_hash, r.row_hash
        checked += 1
    return {"ok": first_break is None, "checked": checked, "head_hash": head, "first_break": first_break}


def verify(db: Any, batch: int = 2000) -> dict:
    """Walk the stored chain in batches."""
    from sqlalchemy import func, select

    from evolvxsi.retention.anchor import load_anchor
    from evolvxsi.route_policy.audit import EvolvXSIAuditEvent as E

    def rows():  # type: ignore[no-untyped-def]
        last = 0
        while True:
            chunk = list(db.scalars(select(E).where(E.row_hash.is_not(None), E.id > last).order_by(E.id.asc()).limit(batch)))
            if not chunk:
                return
            yield from chunk
            last = chunk[-1].id

    out = check_rows(rows(), load_anchor())
    out["unhashed_rows"] = int(db.scalar(select(func.count()).select_from(E).where(E.row_hash.is_(None))) or 0)
    return out
