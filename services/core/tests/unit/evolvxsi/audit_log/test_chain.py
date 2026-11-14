"""The hash chain's rules, on rows held in memory (no database)."""

import datetime
from types import SimpleNamespace

from evolvxsi.governance.audit_log.chain import GENESIS, check_rows, link


def _chain(n: int, start_prev: str = GENESIS, start_id: int = 1) -> list[SimpleNamespace]:
    rows, prev = [], start_prev
    for i in range(n):
        r = SimpleNamespace(id=start_id + i, created_at=datetime.datetime(2026, 11, 12, 10, i, tzinfo=datetime.timezone.utc), action="a", outcome="success",
                            actor_user_id=None, actor_email="x@example.com", resource_type=None, resource_id=None, summary=f"event {i}", details={"i": i}, prev_hash=prev)
        r.row_hash = link(prev, r)
        rows.append(r)
        prev = r.row_hash
    return rows


def test_an_untouched_chain_verifies_and_reports_its_head() -> None:
    rows = _chain(5)
    out = check_rows(rows, None)
    assert out["ok"] and out["checked"] == 5 and out["head_hash"] == rows[-1].row_hash and out["first_break"] is None


def test_changing_any_field_is_caught_at_that_row() -> None:
    for field, value in [("summary", "edited"), ("actor_email", "someone@else"), ("details", {"i": 99}), ("outcome", "denied"),
                         ("created_at", datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc))]:
        rows = _chain(5)
        setattr(rows[2], field, value)
        out = check_rows(rows, None)
        assert not out["ok"] and out["first_break"]["id"] == rows[2].id and "content" in out["first_break"]["reason"], field


def test_removing_a_middle_row_is_caught_at_the_next_one() -> None:
    rows = _chain(5)
    out = check_rows(rows[:2] + rows[3:], None)
    assert not out["ok"] and out["first_break"]["id"] == rows[3].id and "link" in out["first_break"]["reason"]


def test_removing_the_start_without_a_recorded_anchor_is_caught() -> None:
    assert not check_rows(_chain(5)[2:], None)["ok"]


def test_a_prune_that_records_its_anchor_leaves_a_verifiable_chain() -> None:
    rows = _chain(6)
    anchor = rows[2].row_hash  # the last row the prune removed
    assert check_rows(rows[3:], anchor)["ok"]
    assert not check_rows(rows[3:], rows[1].row_hash)["ok"], "the wrong anchor does not verify"


def test_removing_the_newest_rows_is_not_detected_here() -> None:
    """The documented limit: only a head hash kept elsewhere reveals this."""
    rows = _chain(5)
    assert check_rows(rows[:3], None)["ok"] and check_rows(rows[:3], None)["head_hash"] != rows[-1].row_hash


def test_the_hash_depends_on_the_previous_hash() -> None:
    r = _chain(1)[0]
    assert link("a" * 64, r) != link("b" * 64, r)
