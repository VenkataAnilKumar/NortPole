from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nortpole.db.models import Base


class NortPolePackSigner(Base):
    __tablename__ = "nortpole_pack_signer"

    key_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    public_key: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False, default="")
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NortPolePackVersion(Base):
    """One installed version of one pack. At most one version of a pack is
    active; activating another is an upgrade or a rollback."""

    __tablename__ = "nortpole_pack_version"
    __table_args__ = (UniqueConstraint("pack_id", "version", name="uq_nortpole_pack_version"),)

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    # The manifest with every default filled in: what the product reads.
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # The exact canonical JSON that was signed and hashed (sorted keys, no whitespace, UTF-8). Kept as text, not
    # JSONB, so the bytes come back unchanged and the signature and digest can be re-checked from the database.
    # Null on a version installed before this was kept whose original bytes could not be recovered.
    signed_manifest: Mapped[str | None] = mapped_column(Text, nullable=True)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signer_key_id: Mapped[str] = mapped_column(String(80), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    installed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NortPolePackEvaluation(Base):
    """The latest evaluation of one pack version on one model."""

    __tablename__ = "nortpole_pack_eval"
    __table_args__ = (UniqueConstraint("pack_id", "version", "model_configuration_id", name="uq_nortpole_pack_eval"),)

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    model_configuration_id: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    route_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cases_total: Mapped[int] = mapped_column(Integer, nullable=False)
    cases_passed: Mapped[int] = mapped_column(Integer, nullable=False)
    details: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    run_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NortPolePackTransfer(Base):
    """An administrator's approval to let another signer publish new versions of a pack the current owner signs. It lets one
    publish by that signer through, and goes away once that signer has published (the signer then owns the pack)."""

    __tablename__ = "nortpole_pack_transfer"

    pack_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    to_key_id: Mapped[str] = mapped_column(String(80), nullable=False)
    approved_by_email: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
