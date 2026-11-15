from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from nortpole.db.models import Base


class NortPoleWorkflowSchedule(Base):
    """A saved workflow and a cadence. It belongs to one person and every run is made as that person. A run drafts the
    plan and stops; nothing runs further without the owner's yes."""

    __tablename__ = "nortpole_workflow_schedule"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    pack_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pack_template: Mapped[str | None] = mapped_column(String(64), nullable=True)
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


class NortPoleWorkflowRun(Base):
    """One firing of a schedule: what happened and why. Holds no request text."""

    __tablename__ = "nortpole_workflow_run"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("nortpole_workflow_schedule.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("nortpole_task.id", ondelete="SET NULL"), nullable=True)
    fired_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)  # plan_ready plan_failed skipped paused
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    route_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
