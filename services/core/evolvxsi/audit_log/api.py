from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.route_policy.audit import EvolvXSIAuditEvent

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
