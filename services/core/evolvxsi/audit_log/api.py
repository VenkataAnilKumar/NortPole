from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.route_policy.audit import EvolvXSIAuditEvent, record_audit
from evolvxsi.utils.audit import AuditAction, AuditOutcome

router = APIRouter(prefix="/admin/audit")
MAX_PAGE = 200


class AuditRow(BaseModel):
    id: int
    created_at: str
    action: str
    outcome: str
    actor_email: str | None
    resource_type: str | None
    resource_id: str | None
    summary: str
    details: dict | None


class AuditPage(BaseModel):
    events: list[AuditRow]
    # Pass as `before_id` to get the next (older) page; None when there is no more.
    next_before_id: int | None
    actions: list[str]


def _like(term: str) -> str:
    # Escape LIKE wildcards so a search for "100%" means those characters.
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("")
def list_events(
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    before_id: int | None = Query(None, ge=1),
    action_prefix: str | None = Query(None, max_length=60),
    outcome: str | None = Query(None, pattern="^(success|failure|denied)$"),
    actor: str | None = Query(None, max_length=200),
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> AuditPage:
    """Newest first, filtered, paged by id. Only administrators may read it."""
    stmt = select(EvolvXSIAuditEvent).order_by(EvolvXSIAuditEvent.id.desc())
    if before_id is not None:
        stmt = stmt.where(EvolvXSIAuditEvent.id < before_id)
    if action_prefix:
        stmt = stmt.where(EvolvXSIAuditEvent.action.like(_like(action_prefix)[1:], escape="\\"))  # prefix match
    if outcome:
        stmt = stmt.where(EvolvXSIAuditEvent.outcome == outcome)
    if actor:
        stmt = stmt.where(EvolvXSIAuditEvent.actor_email.ilike(_like(actor), escape="\\"))
    rows = list(db_session.scalars(stmt.limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    actions = sorted(db_session.scalars(select(distinct(EvolvXSIAuditEvent.action))))
    return AuditPage(
        events=[
            AuditRow(
                id=e.id, created_at=e.created_at.isoformat(), action=e.action, outcome=e.outcome, actor_email=e.actor_email,
                resource_type=e.resource_type, resource_id=e.resource_id, summary=e.summary, details=e.details,
            )
            for e in rows
        ],
        next_before_id=rows[-1].id if more and rows else None,
        actions=actions,
    )


EXPORT_MAX_ROWS = 50_000
_CSV_FIELDS = ["id", "created_at", "action", "outcome", "actor_email", "resource_type", "resource_id", "summary", "details", "prev_hash", "row_hash"]


def _csv_cell(value: object) -> str:
    """A spreadsheet runs text that starts with = + - @ as a formula; a leading quote stops that."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.post("/export")
def export_events(
    format: str = Query("json", pattern="^(json|csv)$"),
    since_id: int | None = Query(None, ge=0),
    until_id: int | None = Query(None, ge=1),
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> Response:
    """Download audit events, oldest first, for up to 50,000 rows (use since_id to continue).
    Administrators only; the export is itself written to the audit log (counts and range, not content)."""
    stmt = select(EvolvXSIAuditEvent).order_by(EvolvXSIAuditEvent.id.asc()).limit(EXPORT_MAX_ROWS)
    if since_id is not None:
        stmt = stmt.where(EvolvXSIAuditEvent.id > since_id)
    if until_id is not None:
        stmt = stmt.where(EvolvXSIAuditEvent.id <= until_id)
    rows = [
        {"id": e.id, "created_at": e.created_at.isoformat(), "action": e.action, "outcome": e.outcome, "actor_email": e.actor_email,
         "resource_type": e.resource_type, "resource_id": e.resource_id, "summary": e.summary, "details": e.details,
         "prev_hash": e.prev_hash, "row_hash": e.row_hash}
        for e in db_session.scalars(stmt)
    ]
    record_audit(AuditAction.AUDIT_EXPORT, AuditOutcome.SUCCESS, actor=user, resource_type="audit",
                 summary=f"Exported {len(rows)} audit events as {format}",
                 details={"rows": len(rows), "first_id": rows[0]["id"] if rows else None, "last_id": rows[-1]["id"] if rows else None,
                          "truncated": len(rows) == EXPORT_MAX_ROWS})
    if format == "json":
        return Response(json.dumps(rows, default=str), media_type="application/json",
                        headers={"Content-Disposition": "attachment; filename=audit-export.json"})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_CSV_FIELDS)
    for r in rows:
        w.writerow([_csv_cell(json.dumps(r[f]) if f == "details" and r[f] is not None else r[f]) for f in _CSV_FIELDS])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit-export.csv"})


@router.get("/verify")
def verify_chain(
    anchor: str | None = Query(None, max_length=100, description="A head saved earlier, as id:hash"),
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> dict:
    """Check the audit hash chain. Detects an edited row or one removed from the middle. It detects removal of the
    newest rows only when `anchor` (a head saved earlier somewhere this machine's administrators cannot change) is given:
    the answer then also says whether that event is still there."""
    from evolvxsi.audit_log.chain import check_anchor, verify_full

    out = verify_full(db_session)
    if anchor:
        out["anchor_check"] = check_anchor(db_session, anchor)
    return out


@router.get("/head")
def audit_head(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> dict:
    """The newest hashed event, as `reference` (id:hash). Keep it off this machine and pass it to /verify later."""
    from evolvxsi.audit_log.chain import head

    return head(db_session)
