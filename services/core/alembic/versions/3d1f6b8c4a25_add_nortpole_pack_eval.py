"""add nortpole_pack_eval

Revision ID: 3d1f6b8c4a25
Revises: 2c9e5a7b3f14
Create Date: 2026-11-13 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "3d1f6b8c4a25"
down_revision = "2c9e5a7b3f14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nortpole_pack_eval",
        sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pack_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("model_configuration_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("route_kind", sa.String(length=20), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("cases_total", sa.Integer(), nullable=False),
        sa.Column("cases_passed", sa.Integer(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pack_id", "version", "model_configuration_id", name="uq_nortpole_pack_eval"),
    )
    op.create_index("ix_nortpole_pack_eval_pack_id", "nortpole_pack_eval", ["pack_id"])


def downgrade() -> None:
    op.drop_index("ix_nortpole_pack_eval_pack_id", table_name="nortpole_pack_eval")
    op.drop_table("nortpole_pack_eval")
