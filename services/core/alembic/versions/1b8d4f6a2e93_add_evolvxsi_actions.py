"""add evolvxsi_action_target and evolvxsi_action

Revision ID: 1b8d4f6a2e93
Revises: 0a5c3e9b7d21
Create Date: 2026-11-12 23:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "1b8d4f6a2e93"
down_revision = "0a5c3e9b7d21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evolvxsi_action_target",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="webhook"),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("allowed_data_classes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "evolvxsi_action",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evolvxsi_task.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("evolvxsi_action_target.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_name", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="proposed"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_status", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_evolvxsi_action_task_id", "evolvxsi_action", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_evolvxsi_action_task_id", table_name="evolvxsi_action")
    op.drop_table("evolvxsi_action")
    op.drop_table("evolvxsi_action_target")
