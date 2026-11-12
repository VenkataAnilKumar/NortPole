from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from evolvxsi.db.models import Base


class EvolvXSIPackSigner(Base):
    __tablename__ = "evolvxsi_pack_signer"

    key_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    public_key: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False, default="")
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EvolvXSIPackVersion(Base):
    """One installed version of one pack. At most one version of a pack is
    active; activating another is an upgrade or a rollback."""

    __tablename__ = "evolvxsi_pack_version"
    __table_args__ = (UniqueConstraint("pack_id", "version", name="uq_evolvxsi_pack_version"),)

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signer_key_id: Mapped[str] = mapped_column(String(80), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    installed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
