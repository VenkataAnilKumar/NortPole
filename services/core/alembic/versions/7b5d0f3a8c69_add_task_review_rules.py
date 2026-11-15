"""add nortpole_task.review_rules

Revision ID: 7b5d0f3a8c69
Revises: 6a4c9e2f7b58
Create Date: 2026-11-13 16:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "7b5d0f3a8c69"
down_revision = "6a4c9e2f7b58"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nortpole_task", sa.Column("review_rules", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("nortpole_task", "review_rules")
