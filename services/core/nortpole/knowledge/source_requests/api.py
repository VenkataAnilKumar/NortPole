"""Discover and requests. Anyone signed in sees what could be added and asks for it; an administrator decides. A
decision is a record only: approving does not connect, activate or allow anything by itself."""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.configs.constants import NotificationType
from nortpole.db.notification import create_notification
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.audit import record_audit
from nortpole.knowledge.source_requests import catalog
from nortpole.knowledge.source_requests.models import NortPoleSourceRequest
from nortpole.utils.audit import AuditAction, AuditOutcome
from nortpole.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter()

MAX_PENDING_PER_PERSON = 20
# Where an administrator turns each kind on after approving.
WHERE = {"connector": "/admin/connectors", "skill": "/admin/packs", "plugin": "/admin/tool-catalog"}


class RequestView(BaseModel):
    id: UUID
    kind: str
    item_key: str
    item_name: str
    reason: str
    state: str
    requested_by_email: str
    decided_by_email: str | None
    decision_note: str
    created_at: datetime.datetime
    decided_at: datetime.datetime | None
    manage_at: str


class DiscoverItem(BaseModel):
    kind: str
    key: str
    name: str
    description: str
    why_approval: str
    my_request: RequestView | None = None


class DiscoverView(BaseModel):
    items: list[DiscoverItem]
    my_requests: list[RequestView]


class NewRequest(BaseModel):
    kind: str
    item_key: str = Field(max_length=120)
    reason: str = Field(default="", max_length=500)


class Decision(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=500)


def _view(r: NortPoleSourceRequest) -> RequestView:
    return RequestView(id=r.id, kind=r.kind, item_key=r.item_key, item_name=r.item_name, reason=r.reason, state=r.state,
                       requested_by_email=r.requested_by_email, decided_by_email=r.decided_by_email, decision_note=r.decision_note,
                       created_at=r.created_at, decided_at=r.decided_at, manage_at=WHERE.get(r.kind, "/admin/approvals"))


def _mine(db: Session, user: User) -> list[NortPoleSourceRequest]:
    return list(db.scalars(select(NortPoleSourceRequest).where(NortPoleSourceRequest.requested_by_id == user.id)
                           .order_by(NortPoleSourceRequest.created_at.desc()).limit(100)))


@router.get("/sources/discover")
def get_discover(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> DiscoverView:
    mine = _mine(db_session, user)
    latest: dict[tuple[str, str], NortPoleSourceRequest] = {}
    for r in mine:  # newest first, so the first seen is the latest
        latest.setdefault((r.kind, r.item_key), r)
    items = []
    for i in catalog.discover(db_session):
        r = latest.get((i.kind, i.key))
        items.append(DiscoverItem(kind=i.kind, key=i.key, name=i.name, description=i.description, why_approval=i.why_approval,
                                  my_request=_view(r) if r and r.state != "withdrawn" else None))
    return DiscoverView(items=items, my_requests=[_view(r) for r in mine[:20]])


@router.post("/sources/requests")
def create_request(
    body: NewRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> RequestView:
    if body.kind not in catalog.KINDS:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Unknown kind of request.")
    item = catalog.find(db_session, body.kind, body.item_key)
    if item is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "That is not on the Discover page: it may already be on.")
    pending = select(NortPoleSourceRequest).where(NortPoleSourceRequest.requested_by_id == user.id, NortPoleSourceRequest.state == "pending")
    if db_session.scalar(pending.where(NortPoleSourceRequest.kind == body.kind, NortPoleSourceRequest.item_key == body.item_key)):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "You have already asked for this; it is waiting for an administrator.")
    if (db_session.scalar(select(func.count()).select_from(pending.subquery())) or 0) >= MAX_PENDING_PER_PERSON:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Too many of your requests are waiting. Withdraw one or wait for a decision.")
    r = NortPoleSourceRequest(kind=body.kind, item_key=item.key, item_name=item.name, reason=body.reason.strip(),
                              requested_by_id=user.id, requested_by_email=user.email)
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    # The reason is the person's own text; the audit records what was asked for, not why.
    record_audit(AuditAction.SOURCE_REQUEST, AuditOutcome.SUCCESS, actor=user, summary=f"Asked for {item.kind} {item.name}",
                 details={"kind": item.kind, "item": item.key, "state": "pending"}, resource_type="source_request", resource_id=str(r.id))
    return _view(r)


@router.post("/sources/requests/{request_id}/withdraw")
def withdraw_request(
    request_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> RequestView:
    r = db_session.get(NortPoleSourceRequest, request_id)
    if r is None or r.requested_by_id != user.id:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Request not found.")
    if r.state != "pending":
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Only a waiting request can be withdrawn.")
    r.state, r.decided_at = "withdrawn", datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()
    record_audit(AuditAction.SOURCE_REQUEST, AuditOutcome.SUCCESS, actor=user, summary=f"Withdrew request for {r.kind} {r.item_name}",
                 details={"kind": r.kind, "item": r.item_key, "state": "withdrawn"}, resource_type="source_request", resource_id=str(r.id))
    return _view(r)


class AdminRequests(BaseModel):
    pending: list[RequestView]
    recent: list[RequestView]


@router.get("/admin/source-requests")
def list_requests(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> AdminRequests:
    q = select(NortPoleSourceRequest)
    pending = db_session.scalars(q.where(NortPoleSourceRequest.state == "pending").order_by(NortPoleSourceRequest.created_at)).all()
    recent = db_session.scalars(q.where(NortPoleSourceRequest.state.in_(("approved", "declined")))
                                .order_by(NortPoleSourceRequest.decided_at.desc()).limit(10)).all()
    return AdminRequests(pending=[_view(r) for r in pending], recent=[_view(r) for r in recent])


@router.post("/admin/source-requests/{request_id}/decide")
def decide_request(
    request_id: UUID,
    body: Decision,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> RequestView:
    r = db_session.get(NortPoleSourceRequest, request_id)
    if r is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Request not found.")
    if r.state != "pending":
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This request has already been decided or withdrawn.")
    r.state = "approved" if body.approve else "declined"
    r.decided_by_email, r.decision_note = user.email, body.note.strip()
    r.decided_at = datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()
    if r.requested_by_id is not None:
        # Tell the person in their Inbox (Updates). Best effort: the decision stands even if this fails.
        try:
            verdict = "approved" if body.approve else "declined"
            ready = "You can install it now from Sources." if r.item_key.startswith(catalog.INTEGRATION_PREFIX) else "An administrator will set it up."
            what = ready if body.approve else "It was not added."
            create_notification(user_id=r.requested_by_id, notif_type=NotificationType.SOURCE_REQUEST_DECIDED, db_session=db_session,
                                title=f"Your request for {r.item_name} was {verdict}",
                                description=f"{what}{' Note: ' + r.decision_note if r.decision_note else ''}",
                                additional_data={"request_id": str(r.id)})
        except Exception:
            logger.exception("Could not notify the requester of a decided source request %s", r.id)
            db_session.rollback()
    record_audit(AuditAction.SOURCE_REQUEST_DECIDE, AuditOutcome.SUCCESS, actor=user,
                 summary=f"{'Approved' if body.approve else 'Declined'} request for {r.kind} {r.item_name} from {r.requested_by_email}",
                 details={"kind": r.kind, "item": r.item_key, "state": r.state}, resource_type="source_request", resource_id=str(r.id))
    return _view(r)
