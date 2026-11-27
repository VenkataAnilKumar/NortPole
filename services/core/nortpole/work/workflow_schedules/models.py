from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import (
    BigInteger,
    Boolean,
    ColumnElement,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    and_,
    cast,
    false,
    func,
    or_,
    true,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from nortpole.db.models import Base
from nortpole.db.pydantic_type import PydanticType


class DriveCsvSource(BaseModel):
    app_id: int = Field(gt=0)
    folder_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    filename_pattern: str = Field(default="*.csv", pattern=r"\S", max_length=200)


class DriveRunSource(BaseModel):
    app_id: int
    folder_id: str
    file_id: str
    version: str
    file_name: str
    library_name: str
    policy_title: str


class ExpenseReviewInputs(BaseModel):
    library_id: int = Field(gt=0)
    csv_file_id: uuid.UUID | None = None
    drive_source: DriveCsvSource | None = None
    policy_title: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def validate_source(self) -> ExpenseReviewInputs:
        if (self.csv_file_id is None) == (self.drive_source is None):
            raise ValueError("Choose one CSV source.")
        return self


class NortPoleWorkflowSchedule(Base):
    """A saved workflow and cadence. Each run uses the owner's permissions."""

    __tablename__ = "nortpole_workflow_schedule"
    __table_args__ = (
        Index("ix_workflow_schedule_sources", "source_scan_at", "id",
              postgresql_where=text("cadence = 'source' AND state = 'active'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    notify_plan_ready: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    notify_needs_review: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    notify_run_failed: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    notify_run_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    pack_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pack_template: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expense_review: Mapped[ExpenseReviewInputs | None] = mapped_column(
        PydanticType(ExpenseReviewInputs, sanitize_strings=True), nullable=True
    )
    # The draft each run starts from (a snapshot; editing the schedule changes future runs only).
    title: Mapped[str] = mapped_column(String, nullable=False)
    request: Mapped[str] = mapped_column(Text, nullable=False)
    desired_output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cadence: Mapped[str] = mapped_column(String(20), nullable=False)  # once daily weekdays weekly monthly
    at_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM in the owner's time zone
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0 Monday … 6 Sunday, for weekly
    month_day: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 … 28, for monthly
    run_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)  # for once
    spread_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 … 4, so equal times do not fire together
    source_library_id: Mapped[int | None] = mapped_column(Integer)
    source_since: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    source_scan_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active paused ended
    pause_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    unaccepted_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skip_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shared_with_groups: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)  # group names (R6b)
    copied_from_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    last_fired_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


def shared_schedule_clause(group_names: set[str]) -> ColumnElement[bool]:
    schedule = NortPoleWorkflowSchedule
    return and_(
        schedule.state != "ended",
        schedule.cadence != "source",
        or_(
            schedule.expense_review.is_(None),
            cast(schedule.expense_review, JSONB) == JSONB.NULL,
        ),
        or_(
            false(),
            *(schedule.shared_with_groups.contains([name]) for name in sorted(group_names)),
        ),
    )


class NortPoleWorkflowRun(Base):
    """One firing of a schedule: what happened and why. Holds no request text."""

    __tablename__ = "nortpole_workflow_run"
    __table_args__ = (
        UniqueConstraint("retry_of_id", name="uq_workflow_run_retry_of"),
        UniqueConstraint("schedule_id", "source_event_id", name="uq_workflow_run_source_event"),
        Index("ix_workflow_run_queued", "fired_at", postgresql_where=text("outcome = 'queued' AND trigger = 'timer'")),
        Index("ix_workflow_run_source_queued", "fired_at", postgresql_where=text("outcome = 'queued' AND trigger = 'source'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("nortpole_workflow_schedule.id", ondelete="CASCADE"), nullable=False, index=True)
    retry_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("nortpole_workflow_run.id", name="fk_workflow_run_retry_of", ondelete="SET NULL"),
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("nortpole_task.id", ondelete="SET NULL"), nullable=True)
    chat_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chat_session.id", name="fk_workflow_run_chat_session", ondelete="SET NULL"), nullable=True, index=True
    )
    chat_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_message.id", name="fk_workflow_run_chat_result", ondelete="SET NULL"),
    )
    drive_source: Mapped[DriveRunSource | None] = mapped_column(
        PydanticType(DriveRunSource), nullable=True
    )
    fired_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    trigger: Mapped[str | None] = mapped_column(String(16))
    source_event_id: Mapped[int | None] = mapped_column(BigInteger)
    source_library_id: Mapped[int | None] = mapped_column(Integer)
    source_document_id: Mapped[str | None] = mapped_column(Text)
    source_content_hash: Mapped[str | None] = mapped_column(String)
    schedule_version: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    route_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class KnowledgeChange(Base):
    """An acknowledged content change in the active Knowledge index."""

    __tablename__ = "nortpole_knowledge_change"
    __table_args__ = (
        Index("ix_knowledge_change_time", "created_at"),
        Index("ix_knowledge_change_document", "document_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    document_id: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class KnowledgeTriggerInput(BaseModel):
    library_id: int
    document_id: str
    content_hash: str
