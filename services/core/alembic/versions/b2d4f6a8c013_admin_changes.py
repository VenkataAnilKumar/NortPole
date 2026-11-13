"""administrator changes that wait for a second administrator

Revision ID: b2d4f6a8c013
Revises: a1c3e5f7b902
Create Date: 2026-11-13 23:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2d4f6a8c013"
down_revision = "a1c3e5f7b902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evolvxsi_admin_change",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("proposed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("proposed_by_email", sa.String(), nullable=False),
        sa.Column("decided_by_email", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_evolvxsi_admin_change_state", "evolvxsi_admin_change", ["state"])


def downgrade() -> None:
    op.drop_index("ix_evolvxsi_admin_change_state", table_name="evolvxsi_admin_change")
    op.drop_table("evolvxsi_admin_change")
