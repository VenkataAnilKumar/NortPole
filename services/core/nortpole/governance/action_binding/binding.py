"""Exact-action approval and repeat-safe execution.

Rules (see the delivery plan, A6):

* An approval covers one action: one action name, one target and one payload.
  Changing any of them needs a fresh approval.
* Approval never overrides a policy block. A blocked action stays blocked even
  with a valid approval.
* An approval is used at most once. A completed action is not run again; a
  retry of the same approved action reuses the same idempotency key.
* An approval has a lifetime. After it, it no longer covers anything.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


def canonical_payload(payload: dict[str, Any]) -> str:
    """Stable text form: sorted keys, no whitespace, so equal payloads hash equal
    whatever order the keys arrived in."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def action_fingerprint(action: str, target: str, payload: dict[str, Any]) -> str:
    body = json.dumps(
        {"action": action, "target": target, "payload": canonical_payload(payload)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def idempotency_key(approval_id: str, fingerprint: str) -> str:
    """Same approval and same action give the same key, so a retry cannot
    produce a second external effect."""
    return hashlib.sha256(f"{approval_id}:{fingerprint}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Approval:
    approval_id: str
    fingerprint: str
    approver: str
    approved_at: datetime
    lifetime: timedelta = timedelta(minutes=30)
    used: bool = False


class Verdict(str, Enum):
    ALLOWED = "allowed"
    NO_APPROVAL = "no_approval"
    ACTION_CHANGED = "action_changed"
    EXPIRED = "expired"
    ALREADY_USED = "already_used"
    POLICY_BLOCKED = "policy_blocked"


@dataclass(frozen=True)
class ExecutionDecision:
    verdict: Verdict
    idempotency_key: str | None = None

    @property
    def may_run(self) -> bool:
        return self.verdict is Verdict.ALLOWED


def decide_execution(
    *,
    action: str,
    target: str,
    payload: dict[str, Any],
    approval: Approval | None,
    policy_allows: bool,
    now: datetime | None = None,
    requires_approval: bool = True,
) -> ExecutionDecision:
    """May this exact action run now? Checked in a fixed order: a policy block
    wins over everything, including a valid approval."""
    now = now or datetime.now(timezone.utc)
    if not policy_allows:
        return ExecutionDecision(Verdict.POLICY_BLOCKED)
    fingerprint = action_fingerprint(action, target, payload)
    if not requires_approval:
        return ExecutionDecision(Verdict.ALLOWED, idempotency_key("none", fingerprint))
    if approval is None:
        return ExecutionDecision(Verdict.NO_APPROVAL)
    if approval.fingerprint != fingerprint:
        return ExecutionDecision(Verdict.ACTION_CHANGED)
    if now > approval.approved_at + approval.lifetime:
        return ExecutionDecision(Verdict.EXPIRED)
    if approval.used:
        return ExecutionDecision(Verdict.ALREADY_USED)
    return ExecutionDecision(
        Verdict.ALLOWED, idempotency_key(approval.approval_id, fingerprint)
    )
