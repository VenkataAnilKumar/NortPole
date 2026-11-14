from __future__ import annotations

import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nortpole.governance.redaction.request import NortPoleRedactionCount
from nortpole.governance.retention.settings import Retention, load, save
from nortpole.governance.route_policy.audit import NortPoleAuditEvent, record_audit
from nortpole.governance.route_policy.usage import NortPoleRouteTokens, NortPoleRouteUsage
from nortpole.utils.audit import AuditAction, AuditOutcome


def prune(db: Session, *, now: datetime.datetime | None = None, actor=None, settings: Retention | None = None) -> dict:  # type: ignore[no-untyped-def]
    """Delete what is older than the configured periods. Does nothing under a legal hold.
    The prune itself is recorded in the audit log, after the deletion, so it is never
    removed by the run that wrote it."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    explicit = settings is not None
    r = settings or load()
    if r.legal_hold:
        return {"held": True, "audit_events": 0, "usage_rows": 0, "redaction_rows": 0}
    out = {"held": False, "audit_events": 0, "usage_rows": 0, "redaction_rows": 0}
    if r.audit_days:
        cutoff = now - datetime.timedelta(days=r.audit_days)
        # The last hashed row about to go: its hash is where the surviving chain now starts.
        last_gone = db.scalar(select(NortPoleAuditEvent.row_hash).where(
            NortPoleAuditEvent.created_at < cutoff, NortPoleAuditEvent.row_hash.is_not(None)).order_by(NortPoleAuditEvent.id.desc()).limit(1))
        out["audit_events"] = db.execute(delete(NortPoleAuditEvent).where(NortPoleAuditEvent.created_at < cutoff)).rowcount or 0
    if r.usage_days:
        day = (now - datetime.timedelta(days=r.usage_days)).date()
        # Token and cost counters follow the same period as the request counters and count in the same total.
        out["usage_rows"] = (db.execute(delete(NortPoleRouteUsage).where(NortPoleRouteUsage.day < day)).rowcount or 0) + (
            db.execute(delete(NortPoleRouteTokens).where(NortPoleRouteTokens.day < day)).rowcount or 0)
        out["redaction_rows"] = db.execute(delete(NortPoleRedactionCount).where(NortPoleRedactionCount.day < day)).rowcount or 0
    db.commit()
    if not r.legal_hold and r.audit_days and out["audit_events"] and last_gone:
        from nortpole.governance.retention.anchor import save_anchor

        save_anchor(last_gone)
    summary = f"Pruned {out['audit_events']} audit events, {out['usage_rows']} usage rows, {out['redaction_rows']} redaction rows"
    if not explicit:  # a caller that passes its own settings is not changing the stored ones
        r.last_prune_at, r.last_prune_summary = now.isoformat(), summary
        save(r)
    record_audit(AuditAction.RETENTION_PRUNE, AuditOutcome.SUCCESS, actor=actor, summary=summary, resource_type="retention")
    return out
