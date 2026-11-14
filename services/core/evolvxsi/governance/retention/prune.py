from __future__ import annotations

import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from evolvxsi.governance.redaction.request import EvolvXSIRedactionCount
from evolvxsi.governance.retention.settings import Retention, load, save
from evolvxsi.governance.route_policy.audit import EvolvXSIAuditEvent, record_audit
from evolvxsi.governance.route_policy.usage import EvolvXSIRouteTokens, EvolvXSIRouteUsage
from evolvxsi.utils.audit import AuditAction, AuditOutcome


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
        last_gone = db.scalar(select(EvolvXSIAuditEvent.row_hash).where(
            EvolvXSIAuditEvent.created_at < cutoff, EvolvXSIAuditEvent.row_hash.is_not(None)).order_by(EvolvXSIAuditEvent.id.desc()).limit(1))
        out["audit_events"] = db.execute(delete(EvolvXSIAuditEvent).where(EvolvXSIAuditEvent.created_at < cutoff)).rowcount or 0
    if r.usage_days:
        day = (now - datetime.timedelta(days=r.usage_days)).date()
        # Token and cost counters follow the same period as the request counters and count in the same total.
        out["usage_rows"] = (db.execute(delete(EvolvXSIRouteUsage).where(EvolvXSIRouteUsage.day < day)).rowcount or 0) + (
            db.execute(delete(EvolvXSIRouteTokens).where(EvolvXSIRouteTokens.day < day)).rowcount or 0)
        out["redaction_rows"] = db.execute(delete(EvolvXSIRedactionCount).where(EvolvXSIRedactionCount.day < day)).rowcount or 0
    db.commit()
    if not r.legal_hold and r.audit_days and out["audit_events"] and last_gone:
        from evolvxsi.governance.retention.anchor import save_anchor

        save_anchor(last_gone)
    summary = f"Pruned {out['audit_events']} audit events, {out['usage_rows']} usage rows, {out['redaction_rows']} redaction rows"
    if not explicit:  # a caller that passes its own settings is not changing the stored ones
        r.last_prune_at, r.last_prune_summary = now.isoformat(), summary
        save(r)
    record_audit(AuditAction.RETENTION_PRUNE, AuditOutcome.SUCCESS, actor=actor, summary=summary, resource_type="retention")
    return out
