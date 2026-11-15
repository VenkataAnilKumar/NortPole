"""add nortpole_action_target.tier

Revision ID: 6a4c9e2f7b58
Revises: 5f3b8d1e6a47
Create Date: 2026-11-13 15:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "6a4c9e2f7b58"
down_revision = "5f3b8d1e6a47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nortpole_action_target", sa.Column("tier", sa.String(length=20), nullable=False, server_default="act_with_approval"))


def downgrade() -> None:
    op.drop_column("nortpole_action_target", "tier")
