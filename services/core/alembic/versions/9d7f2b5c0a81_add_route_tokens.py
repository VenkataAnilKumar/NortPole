"""add nortpole_route_tokens

Revision ID: 9d7f2b5c0a81
Revises: 8c6e1a4b9d70
Create Date: 2026-11-13 20:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "9d7f2b5c0a81"
down_revision = "8c6e1a4b9d70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nortpole_route_tokens",
        sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("route_kind", sa.String(length=20), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_cents", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("unpriced_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("day", "route_kind", "provider_id", "model_name", name="uq_nortpole_route_tokens"),
    )


def downgrade() -> None:
    op.drop_table("nortpole_route_tokens")
