from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from nortpole.db.models import Base


class NortPoleIntegrationUse(Base):
    """One person's use of one integration: that they installed it, the settings they chose for the parameters only they
    may set, and (once they connect) their own account. The account is encrypted at rest and is read only to make a call;
    no screen, log or audit row ever shows it."""

    __tablename__ = "nortpole_integration_use"
    __table_args__ = (UniqueConstraint("user_id", "integration_id", name="uq_nortpole_integration_use"),)

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # The definition version the person installed, so a later version can be reviewed before it replaces it.
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # The sealed account (a Fernet token), or null when the person has not connected one.
    credential: Mapped[str | None] = mapped_column(Text, nullable=True)
    installed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    connected_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
