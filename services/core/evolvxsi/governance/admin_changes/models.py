from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from evolvxsi.db.models import Base


class EvolvXSIAdminChange(Base):
    """An administrator change that waits for a second administrator. The payload is the request as it was made;
    nothing in it is a secret (policy settings and retention periods)."""

    __tablename__ = "evolvxsi_admin_change"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # The version of the setting this was based on; if the setting changed since, approval is refused.
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending applied declined cancelled expired failed
    proposed_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    proposed_by_email: Mapped[str] = mapped_column(String, nullable=False)
    decided_by_email: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
