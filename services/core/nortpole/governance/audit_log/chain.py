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

    from nortpole.governance.retention.anchor import load_anchor
    from nortpole.governance.route_policy.audit import NortPoleAuditEvent as E

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


CHECKPOINT_KEY = "nortpole_audit_verified"
FULL_EVERY_HOURS = 24


def _load_checkpoint() -> dict | None:
    try:
        from nortpole.key_value_store.factory import get_kv_store

        v = get_kv_store().load(CHECKPOINT_KEY)
        return v if isinstance(v, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _save_checkpoint(cp: dict) -> None:
    try:
        from nortpole.key_value_store.factory import get_kv_store

        get_kv_store().store(CHECKPOINT_KEY, cp)
    except Exception:  # noqa: BLE001 - a lost checkpoint only means the next check is a full one
        pass


def verify_full(db: Any) -> dict:
    """The whole chain; also records a checkpoint for later quick checks."""
    import datetime

    from sqlalchemy import select

    from nortpole.governance.route_policy.audit import NortPoleAuditEvent as E

    out = verify(db)
    last = db.execute(select(E.id, E.row_hash).where(E.row_hash.is_not(None)).order_by(E.id.desc()).limit(1)).first()
    _save_checkpoint({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "ok": out["ok"], "checked": out["checked"],
                      "first_break": out["first_break"], "last_id": last[0] if last else 0, "last_hash": last[1] if last else None})
    return {**out, "mode": "full", "full_check_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}


def verify_quick(db: Any) -> dict:
    """For pages that load often. Runs the full check if none was done in the last 24 hours, if the last one found a
    break, or if the checkpoint row itself no longer matches; otherwise checks only the events added since. An edit to
    an event before the checkpoint is therefore caught by the next full check (at most a day later), not instantly."""
    import datetime

    from sqlalchemy import func, select

    from nortpole.governance.route_policy.audit import NortPoleAuditEvent as E

    cp = _load_checkpoint()
    now = datetime.datetime.now(datetime.timezone.utc)
    stale = cp is None or not cp.get("ok") or now - datetime.datetime.fromisoformat(cp["at"]) > datetime.timedelta(hours=FULL_EVERY_HOURS)
    if not stale and cp.get("last_id"):
        row = db.get(E, cp["last_id"])
        stale = row is None or row.row_hash != cp.get("last_hash") or link(row.prev_hash, row) != row.row_hash
    if stale:
        return verify_full(db)
    new_rows = list(db.scalars(select(E).where(E.row_hash.is_not(None), E.id > cp.get("last_id", 0)).order_by(E.id.asc())))
    inc = check_rows(new_rows, cp.get("last_hash"))
    unhashed = int(db.scalar(select(func.count()).select_from(E).where(E.row_hash.is_(None))) or 0)
    return {"ok": inc["ok"], "checked": cp.get("checked", 0) + inc["checked"], "head_hash": inc["head_hash"] or cp.get("last_hash"),
            "first_break": inc["first_break"], "unhashed_rows": unhashed, "mode": "since the last full check", "full_check_at": cp["at"]}


def head(db: Any) -> dict:
    """The newest hashed event. Save `reference` somewhere an administrator of this machine cannot change (another
    system, a mailbox, a ticket); `check_anchor` compares it later and shows if newer events were removed."""
    from sqlalchemy import func, select

    from nortpole.governance.route_policy.audit import NortPoleAuditEvent as E

    last = db.execute(select(E.id, E.row_hash, E.created_at).where(E.row_hash.is_not(None)).order_by(E.id.desc()).limit(1)).first()
    count = int(db.scalar(select(func.count()).select_from(E).where(E.row_hash.is_not(None))) or 0)
    if last is None:
        return {"head_id": None, "head_hash": None, "reference": None, "hashed_rows": 0, "head_at": None}
    return {"head_id": last[0], "head_hash": last[1], "reference": f"{last[0]}:{last[1]}", "hashed_rows": count,
            "head_at": last[2].isoformat()}


def check_anchor(db: Any, reference: str) -> dict:
    """Compare a head saved earlier (`id:hash`, from `head` or from an event's log line) with the stored log.
    `ok` is True when that event is still there and unchanged, False when newer events seem to be gone or it changed,
    and None when it is older than the oldest event kept (retention removed it, so nothing can be compared)."""
    from sqlalchemy import func, select

    from nortpole.governance.route_policy.audit import NortPoleAuditEvent as E

    text = (reference or "").strip()
    id_part, _, hash_part = text.partition(":")
    if not (id_part.isdigit() and int(id_part) > 0 and len(hash_part) == 64 and all(c in "0123456789abcdef" for c in hash_part)):
        return {"ok": False, "status": "invalid", "message": "The saved head must look like 123:<64 hexadecimal characters>."}
    event_id = int(id_part)
    row = db.get(E, event_id)
    if row is not None:
        if row.row_hash is None:
            return {"ok": None, "status": "not_chained", "message": f"Event {event_id} has no hash (it was written before the chain existed), so it cannot be compared."}
        if row.row_hash == hash_part:
            return {"ok": True, "status": "found", "message": f"Event {event_id} is still in the log and unchanged."}
        return {"ok": False, "status": "changed", "message": f"Event {event_id} is in the log but its hash is different from the saved one."}
    lo, hi = db.execute(select(func.min(E.id), func.max(E.id)).where(E.row_hash.is_not(None))).one()
    if hi is None or event_id > hi:
        return {"ok": False, "status": "newer_than_log",
                "message": f"The saved head (event {event_id}) is newer than anything in the log: newer events were removed, or an older backup was restored."}
    if event_id < lo:
        return {"ok": None, "status": "pruned",
                "message": f"The saved head (event {event_id}) is older than the oldest kept event ({lo}); retention removed it, so it cannot be compared."}
    return {"ok": False, "status": "missing", "message": f"Event {event_id} was in the log's range but is gone: an event was removed."}
