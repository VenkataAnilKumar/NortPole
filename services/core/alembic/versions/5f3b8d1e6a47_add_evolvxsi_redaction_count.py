"""add evolvxsi_redaction_count

Revision ID: 5f3b8d1e6a47
Revises: 4e2a7c9d5b36
Create Date: 2026-11-13 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "5f3b8d1e6a47"
down_revision = "4e2a7c9d5b36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evolvxsi_redaction_count",
        sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("route_kind", sa.String(length=20), nullable=False),
        sa.Column("data_kind", sa.String(length=20), nullable=False),
        sa.Column("items", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("day", "route_kind", "data_kind", name="uq_evolvxsi_redaction_count"),
    )


def downgrade() -> None:
    op.drop_table("evolvxsi_redaction_count")
