"""The audit hash chain on the real database: it links, it catches edits and removals, it survives a prune."""

import threading
import uuid

import pytest
from sqlalchemy import text

from evolvxsi.audit_log.chain import check_rows, verify
from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.route_policy.audit import EvolvXSIAuditEvent, record_audit
from evolvxsi.utils.audit import AuditAction, AuditOutcome
from tests.evolvxsi_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the audit chain columns")

TAG = f"chain-{uuid.uuid4().hex[:8]}"


def _write(n: int) -> None:
    if not FIRST_ID:
        with get_session_with_current_tenant() as s:
            FIRST_ID.append((s.query(EvolvXSIAuditEvent.id).order_by(EvolvXSIAuditEvent.id.desc()).limit(1).scalar() or 0) + 1)
    for i in range(n):
        record_audit(AuditAction.RETENTION_CHANGE, AuditOutcome.SUCCESS, actor=None, summary=f"{TAG} event {i}", details={"i": i, "tag": TAG})


FIRST_ID: list[int] = []  # the first event this module wrote; the chain is checked from there on


def _fresh_verify(s):  # type: ignore[no-untyped-def]
    """Verify from this module's first event onward. Other tests delete the audit rows they create (the
    product itself never deletes except by prune), so the shared development chain can have old holes."""
    s.expire_all()  # read what is stored, not what this session remembers
    rows = list(s.query(EvolvXSIAuditEvent).filter(EvolvXSIAuditEvent.row_hash.is_not(None), EvolvXSIAuditEvent.id >= FIRST_ID[0]).order_by(EvolvXSIAuditEvent.id))
    return check_rows(rows, rows[0].prev_hash if rows else None)


def _mine(s):  # type: ignore[no-untyped-def]
    return list(s.query(EvolvXSIAuditEvent).filter(EvolvXSIAuditEvent.summary.like(f"{TAG}%")).order_by(EvolvXSIAuditEvent.id))


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
            s.add(EvolvXSIAuditEvent(**saved)); s.commit()
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
