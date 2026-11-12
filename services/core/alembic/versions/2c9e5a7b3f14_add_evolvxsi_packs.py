"""add packs: signers, versions, and the pack a task started from

Revision ID: 2c9e5a7b3f14
Revises: 1b8d4f6a2e93
Create Date: 2026-11-13 09:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2c9e5a7b3f14"
down_revision = "1b8d4f6a2e93"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evolvxsi_pack_signer",
        sa.Column("key_id", sa.String(length=80), primary_key=True),
        sa.Column("public_key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False, server_default=""),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "evolvxsi_pack_version",
        sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pack_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("signer_key_id", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("installed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pack_id", "version", name="uq_evolvxsi_pack_version"),
    )
    op.create_index("ix_evolvxsi_pack_version_pack_id", "evolvxsi_pack_version", ["pack_id"])
    op.add_column("evolvxsi_task", sa.Column("pack_id", sa.String(length=64), nullable=True))
    op.add_column("evolvxsi_task", sa.Column("pack_version", sa.String(length=20), nullable=True))
    op.add_column("evolvxsi_task", sa.Column("pack_template", sa.String(length=64), nullable=True))


def downgrade() -> None:
    for c in ("pack_template", "pack_version", "pack_id"):
        op.drop_column("evolvxsi_task", c)
    op.drop_index("ix_evolvxsi_pack_version_pack_id", table_name="evolvxsi_pack_version")
    op.drop_table("evolvxsi_pack_version")
    op.drop_table("evolvxsi_pack_signer")
