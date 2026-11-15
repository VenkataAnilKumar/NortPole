"""add nortpole_task

Reviewed tasks: a draft that runs nothing, an explicit start, and a plan the
owner reviews before any work.

Revision ID: c4d2e8a91f07
Revises: 9b1e7c3a5d20
Create Date: 2026-11-12 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c4d2e8a91f07"
down_revision = "9b1e7c3a5d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nortpole_task",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("desired_output", sa.Text(), nullable=False, server_default=""),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("plan", postgresql.JSONB(), nullable=True),
        sa.Column("plan_route", sa.String(), nullable=True),
        sa.Column("plan_error", sa.Text(), nullable=True),
        sa.Column("revision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_nortpole_task_owner_id", "nortpole_task", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_nortpole_task_owner_id", table_name="nortpole_task")
    op.drop_table("nortpole_task")
