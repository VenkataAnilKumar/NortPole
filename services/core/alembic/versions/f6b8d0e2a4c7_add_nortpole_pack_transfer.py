"""an administrator's approval for another signer to publish a pack

Revision ID: f6b8d0e2a4c7
Revises: e5a7c9b1d3f6
Create Date: 2026-11-17 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "f6b8d0e2a4c7"
down_revision = "e5a7c9b1d3f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nortpole_pack_transfer",
        sa.Column("pack_id", sa.String(64), primary_key=True),
        sa.Column("to_key_id", sa.String(80), nullable=False),
        sa.Column("approved_by_email", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("nortpole_pack_transfer")
