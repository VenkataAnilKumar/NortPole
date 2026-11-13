from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.models import Base, User
from evolvxsi.route_policy.policy import RoutePolicy
from evolvxsi.utils.audit import (
    AuditActor,
    AuditAction,
    AuditOutcome,
    emit_audit_event,
)
from evolvxsi.utils.logger import setup_logger

logger = setup_logger()


class EvolvXSIAuditEvent(Base):
    """Who, what and when for policy changes and blocked requests. Holds no message content."""

    __tablename__ = "evolvxsi_audit_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # The hash chain (see audit_log/chain.py). Null on rows written before the chain existed.
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


def describe_policy_change(old: RoutePolicy, new: RoutePolicy) -> tuple[str, dict[str, Any]]:
    """Pure: a one-line summary and a structured diff of two policy versions."""
    changes: dict[str, Any] = {}
    parts: list[str] = []
    if old.default_data_class != new.default_data_class:
        changes["default_data_class"] = {"from": old.default_data_class, "to": new.default_data_class}
        parts.append(f"workspace data class {old.default_data_class} to {new.default_data_class}")
    for cls in sorted(set(old.allowed) | set(new.allowed)):
        before, after = set(old.allowed.get(cls, [])), set(new.allowed.get(cls, []))
        if before != after:
            changes.setdefault("allowed", {})[cls] = {
                "added": sorted(after - before),
                "removed": sorted(before - after),
            }
            bits = [f"+{k}" for k in sorted(after - before)] + [f"-{k}" for k in sorted(before - after)]
            parts.append(f"{cls}: {' '.join(bits)}")
    for pid in sorted(set(old.route_kinds) | set(new.route_kinds), key=lambda x: int(x) if x.isdigit() else 0):
        b, a = old.route_kinds.get(pid), new.route_kinds.get(pid)
        if b != a:
            changes.setdefault("route_kinds", {})[pid] = {"from": b, "to": a}
            parts.append(f"provider {pid} {b or 'unset'} to {a or 'unset'}")
    redact_before, redact_after = set(old.redact_route_kinds), set(new.redact_route_kinds)
    if redact_before != redact_after:
        changes["redact_route_kinds"] = {"added": sorted(redact_after - redact_before), "removed": sorted(redact_before - redact_after)}
        bits = [f"+{k}" for k in sorted(redact_after - redact_before)] + [f"-{k}" for k in sorted(redact_before - redact_after)]
        parts.append(f"redaction before sending to: {' '.join(bits)}")
    head = f"Policy v{old.version} to v{new.version}"
    summary = head + (": " + "; ".join(parts) if parts else ": no changes")
    return summary, {"from_version": old.version, "to_version": new.version, "changes": changes}


def record_audit(
    action: AuditAction,
    outcome: AuditOutcome,
    *,
    actor: User | None,
    summary: str,
    details: dict[str, Any] | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
) -> None:
    """Write a durable audit row and emit the log-only audit line. Never raises into the caller."""
    try:
        emit_audit_event(
            action,
            outcome,
            actor=AuditActor(user_id=str(actor.id), email=actor.email) if actor else None,
            resource_type=resource_type,
            resource_id=resource_id,
            extra={"summary": summary},
        )
    except Exception:
        pass
    try:
        # Own session and commit: the row must survive the caller's failed request.
        from sqlalchemy import text

        from evolvxsi.audit_log.chain import GENESIS, LOCK_KEY, link

        with get_session_with_current_tenant() as db:
            # One writer at a time extends the chain; the lock ends with this transaction.
            db.execute(text("select pg_advisory_xact_lock(:k)"), {"k": LOCK_KEY})
            prev = db.scalar(select(EvolvXSIAuditEvent.row_hash).where(EvolvXSIAuditEvent.row_hash.is_not(None)).order_by(EvolvXSIAuditEvent.id.desc()).limit(1))
            row = EvolvXSIAuditEvent(
                action=action.value,
                outcome=outcome.value,
                actor_user_id=str(actor.id) if actor else None,
                actor_email=actor.email if actor else None,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                summary=summary,
                details=details,
            )
            db.add(row)
            db.flush()
            db.refresh(row)  # the stored id, time and details are what the hash covers
            row.prev_hash = prev or _anchor_or_genesis(db, GENESIS)
            row.row_hash = link(row.prev_hash, row)
            db.commit()
            logger.info("audit chain head %s id=%s", row.row_hash, row.id)
    except Exception as exc:  # audit must never break the request
        logger.warning("Could not store audit event %s: %s", action.value, exc)


def _anchor_or_genesis(db: Session, genesis: str) -> str:
    """The hash to chain from when no hashed row exists: the one recorded by the last prune, else genesis."""
    from evolvxsi.retention.anchor import load_anchor

    return load_anchor() or genesis


def list_audit(db: Session, limit: int = 50, action: str | None = None) -> list[EvolvXSIAuditEvent]:
    stmt = select(EvolvXSIAuditEvent).order_by(EvolvXSIAuditEvent.id.desc()).limit(max(1, min(limit, 500)))
    if action:
        stmt = stmt.where(EvolvXSIAuditEvent.action == action)
    return list(db.scalars(stmt).all())
