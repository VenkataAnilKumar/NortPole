"""Persist and execute user-confirmed scheduling requests from Chat."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from nortpole.auth.permissions import has_global_permission, require_permission
from nortpole.background.celery.versioned_apps.client import app as celery_app
from nortpole.configs.constants import NortPoleCeleryQueues, NortPoleCeleryTask
from nortpole.db.engine.sql_engine import get_session, get_session_with_current_tenant
from nortpole.db.enums import Permission
from nortpole.db.models import Base, ChatMessage, ChatSession, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.utils.logger import setup_logger
from nortpole.work.workflow_schedules import api, cadence, runner
from nortpole.work.workflow_schedules.models import NortPoleWorkflowRun, NortPoleWorkflowSchedule
from shared_configs.contextvars import get_current_tenant_id

router = APIRouter()
logger = setup_logger()
EXPIRES_AFTER = runner.CHAT_QUEUE_TIMEOUT
PROCESSING_TIMEOUT = dt.timedelta(minutes=30)


class CreateScheduleArguments(api.When):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cadence: Literal["once", "daily", "weekdays", "weekly", "monthly"]
    name: str = Field(min_length=1, max_length=200)
    request: str = Field(min_length=1, max_length=api.MAX_TEXT)
    desired_output: str = Field(default="", max_length=api.MAX_TEXT)


class RunScheduleArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schedule_name: str = Field(min_length=1, max_length=200)


class ProposalPreview(BaseModel):
    name: str
    request: str
    desired_output: str = ""
    when: str
    next_run_at: dt.datetime | None = None
    private_review: bool = False
    schedule_id: UUID | None = None


class ScheduleProposal(Base):
    __tablename__ = "nortpole_workflow_schedule_proposal"
    __table_args__ = (
        UniqueConstraint("message_id", "fingerprint", name="uq_workflow_proposal_message"),
        Index("ix_workflow_proposal_chat", "chat_id", "created_at"),
        Index("ix_workflow_proposal_queue", "state", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    chat_id: Mapped[UUID] = mapped_column(ForeignKey("chat_session.id", ondelete="CASCADE"))
    message_id: Mapped[int] = mapped_column(ForeignKey("chat_message.id", ondelete="CASCADE"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(10))
    payload: Mapped[dict] = mapped_column(JSONB)
    preview: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(16))
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class ProposalResult(BaseModel):
    schedule_id: UUID | None = None
    run_id: UUID | None = None
    outcome: str | None = None
    detail: str | None = None


class ProposalView(BaseModel):
    id: UUID
    operation: str
    state: str
    preview: ProposalPreview
    result: ProposalResult | None
    expires_at: dt.datetime


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _owned_chat(db: Session, user: User, chat_id: UUID) -> None:
    chat = db.get(ChatSession, chat_id)
    if chat is None or chat.user_id != user.id or chat.deleted or chat.incognito_record_mode is not None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Chat not found.")


def _check_access(db: Session, user: User | None) -> User:
    if not user or not user.is_active or not has_global_permission(user, Permission.BASIC_ACCESS) or not api._allowed(db, user):
        raise NortPoleError(NortPoleErrorCode.INSUFFICIENT_PERMISSIONS, "Scheduling is unavailable for this account.")
    return user


def _view(row: ScheduleProposal, now: dt.datetime) -> ProposalView:
    state = row.state
    if state in {"pending", "queued"} and row.expires_at <= now:
        state = "expired"
    elif state == "running" and row.started_at and row.started_at + PROCESSING_TIMEOUT <= now:
        state = "interrupted"
    return ProposalView(
        id=row.id, operation=row.operation, state=state, expires_at=row.expires_at,
        preview=ProposalPreview.model_validate(row.preview),
        result=ProposalResult.model_validate(row.result) if row.result else None,
    )


def _build_preview(
    db: Session, user: User, args: CreateScheduleArguments | RunScheduleArguments, now: dt.datetime,
) -> tuple[str, dict, ProposalPreview]:
    if isinstance(args, CreateScheduleArguments):
        api._check_when(args)
        api._check_limit(db, user)
        timing = (args.cadence, args.at_time, args.timezone, args.weekday, args.month_day, args.run_on)
        next_run = cadence.next_run(*timing, now)
        if next_run is None:
            raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "That time has already passed.")
        return "create", args.model_dump(mode="json"), ProposalPreview(
            name=args.name, request=args.request, desired_output=args.desired_output,
            when=cadence.describe(*timing), next_run_at=next_run,
        )

    schedule = NortPoleWorkflowSchedule
    matches = db.scalars(select(schedule).where(
        schedule.owner_id == user.id, schedule.state == "active", schedule.cadence != "source",
        func.lower(schedule.name) == args.schedule_name.lower(),
    ).limit(2)).all()
    if len(matches) > 1:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "More than one active schedule has that name. Ask the user to run the intended schedule from Workflows.")
    if not matches:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "No active schedule with that name was found. Ask the user for its exact name.")
    row = matches[0]
    return "run", {"schedule_id": str(row.id), "version": row.version}, ProposalPreview(
        name=row.name, request=row.request, desired_output=row.desired_output,
        when=cadence.describe(row.cadence, row.at_time, row.timezone, row.weekday, row.month_day, row.run_on),
        next_run_at=row.next_run_at, private_review=row.expense_review is not None, schedule_id=row.id,
    )


def propose(
    db: Session, user: User | None, chat_id: UUID, message_id: int,
    args: CreateScheduleArguments | RunScheduleArguments,
) -> None:
    user = _check_access(db, user)
    _owned_chat(db, user, chat_id)
    if not db.scalar(select(ChatMessage.id).where(ChatMessage.id == message_id, ChatMessage.chat_session_id == chat_id)):
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Chat message not found.")
    now = _now()
    operation, payload, preview = _build_preview(db, user, args, now)
    fingerprint = hashlib.sha256(json.dumps([operation, payload], sort_keys=True).encode()).hexdigest()
    db.execute(insert(ScheduleProposal).values(
        id=uuid4(), owner_id=user.id, chat_id=chat_id, message_id=message_id,
        operation=operation, payload=payload, preview=preview.model_dump(mode="json"),
        fingerprint=fingerprint, state="pending", created_at=now, expires_at=now + EXPIRES_AFTER,
    ).on_conflict_do_nothing(constraint="uq_workflow_proposal_message"))
    db.commit()


@router.get("/workflow-schedule-proposals", name="list_workflow_schedule_proposals")
def list_proposals(
    chat_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> list[ProposalView]:
    _owned_chat(db, user, chat_id)
    rows = db.scalars(select(ScheduleProposal).where(
        ScheduleProposal.owner_id == user.id, ScheduleProposal.chat_id == chat_id,
    ).order_by(ScheduleProposal.created_at.desc()).limit(20))
    now = _now()
    return [_view(row, now) for row in rows]


@router.post("/workflow-schedule-proposals/{proposal_id}/{decision}")
def decide_proposal(
    proposal_id: UUID, decision: Literal["confirm", "dismiss"],
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> ProposalView:
    row = db.get(ScheduleProposal, proposal_id)
    if row is None or row.owner_id != user.id:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Schedule proposal not found.")
    _owned_chat(db, user, row.chat_id)
    if decision == "confirm":
        _check_access(db, user)
    now = _now()
    new_state = "queued" if decision == "confirm" else "dismissed"
    changed = db.execute(update(ScheduleProposal).where(
        ScheduleProposal.id == row.id, ScheduleProposal.state == "pending", ScheduleProposal.expires_at > now,
    ).values(state=new_state, expires_at=now + EXPIRES_AFTER if decision == "confirm" else row.expires_at)).rowcount
    if changed and new_state == "queued" and row.operation == "run":
        schedule = api._own(db, UUID(row.payload["schedule_id"]), user)
        if schedule.state != "active" or schedule.version != row.payload["version"]:
            db.rollback()
            raise NortPoleError(NortPoleErrorCode.CONFLICT, "This schedule has changed. Ask Chat for a new proposal.")
        run = runner.queue_run(db, schedule, "chat")
        db.flush()
        row.result = ProposalResult(schedule_id=schedule.id, run_id=run.id).model_dump(mode="json")
    db.commit()
    if changed and new_state == "queued":
        try:
            celery_app.send_task(
                NortPoleCeleryTask.NORTPOLE_EXECUTE_SCHEDULE_PROPOSAL,
                kwargs={"tenant_id": get_current_tenant_id(), "proposal_id": str(proposal_id)},
                queue=NortPoleCeleryQueues.PRIMARY,
                expires=EXPIRES_AFTER.total_seconds(),
                retry=False,
            )
        except Exception:
            logger.exception("Could not dispatch workflow proposal %s. The scheduler will pick it up.", proposal_id)
    return _view(row, now)


def _execute(db: Session, row: ScheduleProposal) -> ProposalResult:
    user = _check_access(db, db.get(User, row.owner_id))
    _owned_chat(db, user, row.chat_id)
    if row.operation == "create":
        args = CreateScheduleArguments.model_validate(row.payload)
        _build_preview(db, user, args, _now())
        saved = api.create_schedule(
            api.NewSchedule(**args.model_dump(), title=args.name),
            user=user, db_session=db,
        )
        return ProposalResult(schedule_id=saved.id)

    schedule_id = UUID(row.payload["schedule_id"])
    schedule = api._own(db, schedule_id, user)
    reserved = ProposalResult.model_validate(row.result or {})
    run = runner.fire_one(
        db, schedule.id, manual_version=row.payload["version"], trigger="chat", run_id=reserved.run_id,
    )
    if run is None:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This workflow run is no longer available.")
    return ProposalResult(schedule_id=schedule_id, run_id=run.id, outcome=run.outcome, detail=run.reason)


def process_confirmed(proposal_id: UUID | None = None, *, limit: int = 10) -> None:
    """Atomically claim each confirmation before executing it. Never replay a claimed operation."""
    for _ in range(limit):
        with get_session_with_current_tenant() as db:
            queued = select(ScheduleProposal).where(
                ScheduleProposal.state == "queued", ScheduleProposal.expires_at > _now(),
            )
            if proposal_id is not None:
                queued = queued.where(ScheduleProposal.id == proposal_id)
            row = db.scalar(queued.order_by(ScheduleProposal.created_at).limit(1).with_for_update(skip_locked=True))
            if row is None:
                return
            row.state = "running"
            row.started_at = _now()
            db.commit()
            state = "completed"
            try:
                result = _execute(db, row)
            except NortPoleError as exc:
                db.rollback()
                state = "failed"
                result = ProposalResult(detail=exc.detail)
            except Exception:
                db.rollback()
                logger.exception("Could not finish workflow proposal %s", row.id)
                state = "interrupted"
                result = ProposalResult(detail="Check Workflows for the outcome before submitting another request.")
            if state != "completed" and row.operation == "run":
                reserved = ProposalResult.model_validate(row.result or {})
                result.schedule_id, result.run_id = reserved.schedule_id, reserved.run_id
                if reserved.run_id:
                    db.execute(update(NortPoleWorkflowRun).where(
                        NortPoleWorkflowRun.id == reserved.run_id, NortPoleWorkflowRun.outcome == "queued",
                    ).values(outcome=state, reason=result.detail, completed_at=_now()))
            db.execute(update(ScheduleProposal).where(ScheduleProposal.id == row.id).values(
                state=state, result=result.model_dump(mode="json"),
            ))
            db.commit()
