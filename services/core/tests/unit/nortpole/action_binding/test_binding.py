from dataclasses import replace
from datetime import datetime, timedelta, timezone

from nortpole.governance.action_binding.binding import (
    Approval,
    Verdict,
    action_fingerprint,
    canonical_payload,
    decide_execution,
)

T0 = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
PAYLOAD = {"to": "a@example.com", "subject": "Brief", "body": "Hello"}


def _approval(**kw) -> Approval:  # type: ignore[no-untyped-def]
    base = Approval(
        approval_id="ap-1",
        fingerprint=action_fingerprint("send_email", "gmail", PAYLOAD),
        approver="lead@example.com",
        approved_at=T0,
    )
    return replace(base, **kw)


def _run(approval, payload=PAYLOAD, **kw):  # type: ignore[no-untyped-def]
    args = dict(
        action="send_email",
        target="gmail",
        payload=payload,
        approval=approval,
        policy_allows=True,
        now=T0 + timedelta(minutes=1),
    )
    args.update(kw)
    return decide_execution(**args)


def test_key_order_does_not_change_the_fingerprint() -> None:
    reordered = {"body": "Hello", "subject": "Brief", "to": "a@example.com"}
    assert canonical_payload(PAYLOAD) == canonical_payload(reordered)
    assert action_fingerprint("a", "t", PAYLOAD) == action_fingerprint("a", "t", reordered)


def test_exact_approved_action_runs_with_a_key() -> None:
    d = _run(_approval())
    assert d.may_run and d.idempotency_key


def test_changed_payload_needs_fresh_approval() -> None:
    d = _run(_approval(), payload={**PAYLOAD, "to": "someone-else@example.com"})
    assert d.verdict is Verdict.ACTION_CHANGED and not d.may_run


def test_changed_action_or_target_needs_fresh_approval() -> None:
    assert _run(_approval(), action="delete_email").verdict is Verdict.ACTION_CHANGED
    assert _run(_approval(), target="outlook").verdict is Verdict.ACTION_CHANGED


def test_no_approval_means_no_run() -> None:
    assert _run(None).verdict is Verdict.NO_APPROVAL


def test_policy_block_beats_a_valid_approval() -> None:
    d = _run(_approval(), policy_allows=False)
    assert d.verdict is Verdict.POLICY_BLOCKED and not d.may_run


def test_expired_approval_covers_nothing() -> None:
    d = _run(_approval(), now=T0 + timedelta(minutes=31))
    assert d.verdict is Verdict.EXPIRED


def test_used_approval_cannot_run_twice() -> None:
    assert _run(_approval(used=True)).verdict is Verdict.ALREADY_USED


def test_retry_reuses_the_same_idempotency_key() -> None:
    first, second = _run(_approval()), _run(_approval())
    assert first.idempotency_key == second.idempotency_key


def test_different_approval_gives_a_different_key() -> None:
    assert _run(_approval()).idempotency_key != _run(_approval(approval_id="ap-2")).idempotency_key


def test_action_that_needs_no_approval_still_respects_policy() -> None:
    assert _run(None, requires_approval=False).may_run
    assert _run(None, requires_approval=False, policy_allows=False).verdict is Verdict.POLICY_BLOCKED
