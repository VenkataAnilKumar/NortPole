"""add draft_claims to evolvxsi_task

Revision ID: f2a9d4c7e015
Revises: e81b6c2d4a93
Create Date: 2026-11-12 20:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f2a9d4c7e015"
down_revision = "e81b6c2d4a93"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evolvxsi_task", sa.Column("draft_claims", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("evolvxsi_task", "draft_claims")
