"""add evolvxsi_route_usage

Revision ID: 4e2a7c9d5b36
Revises: 3d1f6b8c4a25
Create Date: 2026-11-13 13:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "4e2a7c9d5b36"
down_revision = "3d1f6b8c4a25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evolvxsi_route_usage",
        sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("route_kind", sa.String(length=20), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("data_class", sa.String(length=20), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("day", "route_kind", "provider_id", "model_name", "data_class", "purpose", name="uq_evolvxsi_route_usage"),
    )


def downgrade() -> None:
    op.drop_table("evolvxsi_route_usage")
