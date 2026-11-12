from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from evolvxsi.db.models import Base


class EvolvXSITask(Base):
    """One reviewed task. Holds the owner's request and the proposed plan;
    the work itself runs only after an explicit start and an accepted plan."""

    __tablename__ = "evolvxsi_task"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    request: Mapped[str] = mapped_column(Text, nullable=False)
    desired_output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Every change bumps this; writes name the version they were based on.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    plan: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    plan_route: Mapped[str | None] = mapped_column(String, nullable=True)
    plan_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The latest run's draft. Sources are the passages the owner could see
    # when the run gathered them: [{"n", "doc_id", "title", "link"}].
    draft_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    draft_route: Mapped[str | None] = mapped_column(String, nullable=True)
    run_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    drafted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Fingerprint of the draft text and its sources. Approval names it, so an
    # approval covers one exact draft and a new draft needs a new approval.
    draft_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def as_dict(self) -> dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
