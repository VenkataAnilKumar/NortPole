from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from nortpole.db.models import Base


class NortPoleSourceRequest(Base):
    """A person's request for something on the Discover page: a connector type, a pack, or a tool. Approving one
    records the decision only; an administrator still connects, activates or allows the item where it is managed."""

    __tablename__ = "nortpole_source_request"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # connector skill plugin
    item_key: Mapped[str] = mapped_column(String(120), nullable=False)  # connector source, pack id, or tool id
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending approved declined withdrawn
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    requested_by_email: Mapped[str] = mapped_column(String, nullable=False)
    decided_by_email: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
