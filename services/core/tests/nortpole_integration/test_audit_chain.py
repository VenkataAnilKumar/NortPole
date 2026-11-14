"""The audit hash chain on the real database: it links, it catches edits and removals, it survives a prune."""

import threading
import uuid

import pytest
from sqlalchemy import text

from nortpole.governance.audit_log.chain import check_rows, verify
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.governance.route_policy.audit import NortPoleAuditEvent, record_audit
from nortpole.utils.audit import AuditAction, AuditOutcome
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the audit chain columns")

TAG = f"chain-{uuid.uuid4().hex[:8]}"


def _write(n: int) -> None:
    if not FIRST_ID:
        with get_session_with_current_tenant() as s:
            FIRST_ID.append((s.query(NortPoleAuditEvent.id).order_by(NortPoleAuditEvent.id.desc()).limit(1).scalar() or 0) + 1)
    for i in range(n):
        record_audit(AuditAction.RETENTION_CHANGE, AuditOutcome.SUCCESS, actor=None, summary=f"{TAG} event {i}", details={"i": i, "tag": TAG})


FIRST_ID: list[int] = []  # the first event this module wrote; the chain is checked from there on


def _fresh_verify(s):  # type: ignore[no-untyped-def]
    """Verify from this module's first event onward. Other tests delete the audit rows they create (the
    product itself never deletes except by prune), so the shared development chain can have old holes."""
    s.expire_all()  # read what is stored, not what this session remembers
    rows = list(s.query(NortPoleAuditEvent).filter(NortPoleAuditEvent.row_hash.is_not(None), NortPoleAuditEvent.id >= FIRST_ID[0]).order_by(NortPoleAuditEvent.id))
    return check_rows(rows, rows[0].prev_hash if rows else None)


def _mine(s):  # type: ignore[no-untyped-def]
    return list(s.query(NortPoleAuditEvent).filter(NortPoleAuditEvent.summary.like(f"{TAG}%")).order_by(NortPoleAuditEvent.id))


def test_new_events_are_linked_to_the_one_before() -> None:
    _write(3)
    with get_session_with_current_tenant() as s:
        rows = _mine(s)
        assert len(rows) == 3 and all(r.row_hash and len(r.row_hash) == 64 for r in rows)
        assert rows[1].prev_hash == rows[0].row_hash and rows[2].prev_hash == rows[1].row_hash
        v = _fresh_verify(s)
        assert v["ok"] is True and v["checked"] >= 3 and v["head_hash"]
        assert "unhashed_rows" in verify(s), "the stored-chain verify reports rows that predate the chain"


def test_an_edited_row_and_a_removed_row_are_found_and_the_chain_can_be_restored() -> None:
    _write(3)
    with get_session_with_current_tenant() as s:
        a, b, c = _mine(s)[-3:]
        original = b.summary
        s.execute(text("update evolvxsi_audit_event set summary=:x where id=:i"), {"x": "something else", "i": b.id}); s.commit()
        try:
            v = _fresh_verify(s)
            assert not v["ok"] and v["first_break"]["id"] == b.id and "content" in v["first_break"]["reason"]
        finally:  # never leave the shared chain broken
            s.execute(text("update evolvxsi_audit_event set summary=:x where id=:i"), {"x": original, "i": b.id}); s.commit()
        assert _fresh_verify(s)["ok"]

        saved = {col: getattr(b, col) for col in ("id", "created_at", "action", "outcome", "actor_user_id", "actor_email", "resource_type", "resource_id", "summary", "details", "prev_hash", "row_hash")}
        s.execute(text("delete from evolvxsi_audit_event where id=:i"), {"i": b.id}); s.commit()
        try:
            v = _fresh_verify(s)
            assert not v["ok"] and v["first_break"]["id"] == c.id and "link" in v["first_break"]["reason"]
        finally:  # never leave the shared chain with a hole
            s.add(NortPoleAuditEvent(**saved)); s.commit()
        assert _fresh_verify(s)["ok"], "putting the row back restores the chain"


def test_concurrent_writers_do_not_fork_the_chain() -> None:
    threads = [threading.Thread(target=_write, args=(4,)) for _ in range(6)]
    [t.start() for t in threads]; [t.join() for t in threads]
    with get_session_with_current_tenant() as s:
        rows = _mine(s)
        assert len(rows) >= 24
        prevs = [r.prev_hash for r in rows]
        assert len(set(prevs)) == len(prevs), "no two events share a predecessor"
        assert _fresh_verify(s)["ok"]


def test_the_quick_check_does_a_full_one_first_then_only_new_events_and_catches_a_changed_checkpoint() -> None:
    from nortpole.governance.audit_log import chain

    saved = chain._load_checkpoint()
    try:
        _write(2)
        with get_session_with_current_tenant() as s:
            chain._save_checkpoint({"at": "2000-01-01T00:00:00+00:00", "ok": True, "checked": 0, "first_break": None, "last_id": 0, "last_hash": None})
            first = chain.verify_quick(s)
            assert first["mode"] == "full", "an old checkpoint forces a full check"
        _write(2)
        with get_session_with_current_tenant() as s:
            s.expire_all()
            second = chain.verify_quick(s)
            assert second["mode"] == "since the last full check" and second["checked"] == first["checked"] + 2 or not first["ok"]
            cp = chain._load_checkpoint()
            row = s.get(NortPoleAuditEvent, cp["last_id"])
            original = row.summary
            s.execute(text("update evolvxsi_audit_event set summary='changed' where id=:i"), {"i": row.id}); s.commit()
            try:
                s.expire_all()
                assert chain.verify_quick(s)["mode"] == "full", "a changed checkpoint row forces a full check"
            finally:
                s.execute(text("update evolvxsi_audit_event set summary=:x where id=:i"), {"x": original, "i": row.id}); s.commit()
    finally:
        if saved:
            chain._save_checkpoint(saved)


def test_a_saved_head_is_compared_with_the_stored_log() -> None:
    """Non-destructive: it never removes a hashed row, so the shared chain stays intact."""
    from sqlalchemy import func

    from nortpole.governance.audit_log.chain import check_anchor, head

    # An unhashed row, then hashed events after it, then remove the unhashed one: a hole inside the hashed range
    # that was never part of the chain.
    with get_session_with_current_tenant() as s:
        hole = NortPoleAuditEvent(action="retention.change", outcome="success", summary=f"{TAG} hole")
        s.add(hole)
        s.commit()
        hole_id = hole.id
    _write(2)
    with get_session_with_current_tenant() as s:
        s.delete(s.get(NortPoleAuditEvent, hole_id))
        s.commit()
        h = head(s)
        assert h["reference"] == f"{h['head_id']}:{h['head_hash']}" and h["hashed_rows"] > 0

        found = check_anchor(s, h["reference"])
        assert found["ok"] is True and found["status"] == "found"

        wrong = check_anchor(s, f"{h['head_id']}:{'0' * 64}")
        assert wrong["ok"] is False and wrong["status"] == "changed"

        ahead = check_anchor(s, f"{h['head_id'] + 1000}:{'a' * 64}")
        assert ahead["ok"] is False and ahead["status"] == "newer_than_log", "a saved head newer than the log means events are gone"

        gone = check_anchor(s, f"{hole_id}:{'b' * 64}")
        assert gone["ok"] is False and gone["status"] == "missing", "an id inside the range that no longer exists means an event was removed"

        lo = s.query(func.min(NortPoleAuditEvent.id)).filter(NortPoleAuditEvent.row_hash.is_not(None)).scalar()
        if lo and lo > 1:
            old = check_anchor(s, f"{lo - 1}:{'c' * 64}")
            # Either the row is gone (pruned) or it is an old unhashed row (not chained): both cannot be compared.
            assert old["ok"] is None and old["status"] in ("pruned", "not_chained"), "older than the oldest kept event cannot be compared"

    for bad in ("", "abc", "12", "12:xyz", f"0:{'a' * 64}", f"-3:{'a' * 64}", f"5:{'A' * 64}", f"5:{'a' * 63}"):
        assert check_anchor(s, bad)["status"] == "invalid", bad
