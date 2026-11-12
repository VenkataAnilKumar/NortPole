"""add draft versions to evolvxsi_task

Revision ID: 0a5c3e9b7d21
Revises: f2a9d4c7e015
Create Date: 2026-11-12 22:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0a5c3e9b7d21"
down_revision = "f2a9d4c7e015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evolvxsi_task", sa.Column("draft_version", sa.Integer(), nullable=True))
    op.add_column("evolvxsi_task", sa.Column("draft_versions", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("evolvxsi_task", "draft_versions")
    op.drop_column("evolvxsi_task", "draft_version")
