"""Changes an assistant proposes in chat, and the person's yes (decision 0008).

Chat cannot stop to ask a person about one call, so a **write** from chat does not run. It is recorded as one exact action with
its exact arguments, checked as far as it can be without sending anything (so an impossible proposal is refused when it is
made), and shown in the person's Inbox. Only that person can approve it, only while it is pending and before it expires, and
what runs is exactly what was stored, against the same definition version and with every policy check made again. The
arguments are sealed like an account and are never written to the audit log."""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from nortpole.db.models import User
from nortpole.utils.audit import AuditAction, AuditOutcome
from nortpole.work.integrations import executor, registry, secrets, service
from nortpole.work.integrations.models import NortPoleIntegrationProposal
from nortpole.work.integrations.service import IntegrationAccessError

EXPIRES_AFTER = datetime.timedelta(hours=24)
MAX_PENDING = 20
MAX_ARGUMENT_BYTES = 20_000
LIST_LIMIT = 50


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _audit(user: User, action: AuditAction, outcome: AuditOutcome, row: NortPoleIntegrationProposal, summary: str, **details: Any) -> None:
    from nortpole.governance.route_policy.audit import record_audit

    record_audit(
        action, outcome, actor=user, summary=summary,
        details={"integration": row.integration_id, "version": row.integration_version, "action": row.action_id, "proposal": str(row.id), **details},
        resource_type="integration", resource_id=row.integration_id,
    )


def view(row: NortPoleIntegrationProposal) -> dict[str, Any]:
    """What the owner sees, arguments included (they are the person's own data and the thing they are deciding on)."""
    integration = registry.get(row.integration_id)
    try:
        arguments = secrets.unseal(row.arguments)
    except secrets.SecretsError:
        arguments = {}
    return {
        "id": str(row.id), "integration_id": row.integration_id, "integration_name": integration.name if integration else row.integration_id,
        "action_id": row.action_id, "summary": row.summary, "arguments": arguments, "state": effective_state(row), "outcome": row.outcome,
        "created_at": row.created_at, "expires_at": row.expires_at, "decided_at": row.decided_at,
    }


def propose(db: Session, user: User, integration_id: str, action_id: str, arguments: dict[str, Any]) -> NortPoleIntegrationProposal:
    integration, action = service.check_arguments(db, user, integration_id, action_id, arguments)
    if action.effect != "write":
        raise IntegrationAccessError("not_a_write", f"{action.name} only reads; it needs no approval.")
    raw = json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str)
    if len(raw.encode()) > MAX_ARGUMENT_BYTES:
        raise IntegrationAccessError("too_large", "That change is larger than a proposal may be.")
    _expire(db, user)
    pending = db.scalar(select(func.count()).select_from(NortPoleIntegrationProposal).where(
        NortPoleIntegrationProposal.user_id == user.id, NortPoleIntegrationProposal.state == "pending"))
    if (pending or 0) >= MAX_PENDING:
        raise IntegrationAccessError("too_many", "There are already many changes waiting for a yes. Decide those first.")
    try:
        sealed = secrets.seal(json.loads(raw))
    except secrets.SecretsError as exc:
        raise IntegrationAccessError(exc.code, str(exc)) from exc
    row = NortPoleIntegrationProposal(
        user_id=user.id, integration_id=integration.id, integration_version=integration.version, action_id=action.id,
        summary=f"{action.name} in {integration.name}", arguments=sealed, state="pending", expires_at=_now() + EXPIRES_AFTER,
    )
    db.add(row)
    db.commit()
    _audit(user, AuditAction.INTEGRATION_WRITE_PROPOSED, AuditOutcome.SUCCESS, row, f"Proposed: {row.summary}", argument_bytes=len(raw))
    return row


def _expire(db: Session, user: User) -> None:
    db.execute(update(NortPoleIntegrationProposal).where(
        NortPoleIntegrationProposal.user_id == user.id, NortPoleIntegrationProposal.state == "pending",
        NortPoleIntegrationProposal.expires_at < _now()).values(state="expired", decided_at=_now()))
    db.commit()


def effective_state(row: NortPoleIntegrationProposal) -> str:
    """The state as of now: a pending proposal past its time reads as expired even before anything marks it."""
    return "expired" if row.state == "pending" and row.expires_at < _now() else row.state


def list_mine(db: Session, user: User, *, pending_only: bool = False) -> list[NortPoleIntegrationProposal]:
    """Read only (a GET never writes); expiry is worked out when each row is shown."""
    query = (
        select(NortPoleIntegrationProposal)
        .where(NortPoleIntegrationProposal.user_id == user.id)
        .order_by(NortPoleIntegrationProposal.created_at.desc())
    )
    if pending_only:
        return list(db.scalars(query.where(
            NortPoleIntegrationProposal.state == "pending",
            NortPoleIntegrationProposal.expires_at >= _now(),
        )))
    rows = db.scalars(query.limit(LIST_LIMIT)).all()
    return sorted(rows, key=lambda r: effective_state(r) != "pending")


def _own(db: Session, user: User, proposal_id: uuid.UUID) -> NortPoleIntegrationProposal:
    row = db.scalar(select(NortPoleIntegrationProposal).where(NortPoleIntegrationProposal.id == proposal_id, NortPoleIntegrationProposal.user_id == user.id))
    if row is None:
        raise IntegrationAccessError("unknown_proposal", "That change was not found.")
    return row


def decline(db: Session, user: User, proposal_id: uuid.UUID) -> NortPoleIntegrationProposal:
    row = _own(db, user, proposal_id)
    claimed = db.execute(update(NortPoleIntegrationProposal).where(NortPoleIntegrationProposal.id == row.id, NortPoleIntegrationProposal.state == "pending")
                         .values(state="declined", decided_at=_now())).rowcount
    db.commit()
    db.refresh(row)
    if not claimed:
        raise IntegrationAccessError("not_pending", f"That change is already {row.state}.")
    _audit(user, AuditAction.INTEGRATION_WRITE_DECIDED, AuditOutcome.SUCCESS, row, f"Declined: {row.summary}", decision="declined")
    return row


def approve(db: Session, user: User, proposal_id: uuid.UUID, *, transport: executor.Transport | None = None) -> NortPoleIntegrationProposal:
    row = _own(db, user, proposal_id)
    if row.state == "pending" and row.expires_at < _now():
        _expire(db, user)
        db.refresh(row)
    # Claim it before anything is sent, so two approvals (a double click, two tabs) can never run it twice.
    claimed = db.execute(update(NortPoleIntegrationProposal).where(NortPoleIntegrationProposal.id == row.id, NortPoleIntegrationProposal.state == "pending")
                         .values(state="approving", decided_at=_now())).rowcount
    db.commit()
    db.refresh(row)
    if not claimed:
        raise IntegrationAccessError("not_pending", f"That change is already {row.state}.")
    integration = registry.get(row.integration_id)
    outcome, state = "returned", "executed"
    try:
        if integration is None or integration.version != row.integration_version:
            raise IntegrationAccessError("changed", "The integration was updated since this was proposed. Ask again.")
        arguments = secrets.unseal(row.arguments)
        service.call(db, user, row.integration_id, row.action_id, model_params=arguments, transport=transport)
    except (IntegrationAccessError, executor.IntegrationCallError, secrets.SecretsError) as exc:
        outcome, state = getattr(exc, "code", "failed"), "failed"
    row.state, row.outcome = state, outcome
    db.commit()
    _audit(user, AuditAction.INTEGRATION_WRITE_DECIDED, AuditOutcome.SUCCESS if state == "executed" else AuditOutcome.FAILURE, row,
           f"Approved: {row.summary} ({outcome})", decision="approved", result=outcome)
    return row
