"""add draft fields to nortpole_task

The latest run's cited draft and the sources it was drafted from.

Revision ID: d7f3a1c05b12
Revises: c4d2e8a91f07
Create Date: 2026-11-12 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d7f3a1c05b12"
down_revision = "c4d2e8a91f07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nortpole_task", sa.Column("draft_text", sa.Text(), nullable=True))
    op.add_column("nortpole_task", sa.Column("draft_sources", postgresql.JSONB(), nullable=True))
    op.add_column("nortpole_task", sa.Column("draft_route", sa.String(), nullable=True))
    op.add_column("nortpole_task", sa.Column("run_error", sa.Text(), nullable=True))
    op.add_column("nortpole_task", sa.Column("drafted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for c in ("drafted_at", "run_error", "draft_route", "draft_sources", "draft_text"):
        op.drop_column("nortpole_task", c)
