"""scheduled workflows: schedules, runs, and the schedule a task came from

Revision ID: d4f6b8c0e235
Revises: c3e5a7b9d124
Create Date: 2026-11-14 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4f6b8c0e235"
down_revision = "c3e5a7b9d124"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evolvxsi_workflow_schedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("pack_id", sa.String(length=64), nullable=True),
        sa.Column("pack_template", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("desired_output", sa.Text(), nullable=False, server_default=""),
        sa.Column("cadence", sa.String(length=20), nullable=False),
        sa.Column("at_time", sa.String(length=5), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("month_day", sa.Integer(), nullable=True),
        sa.Column("run_on", sa.Date(), nullable=True),
        sa.Column("spread_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("pause_reason", sa.String(length=30), nullable=True),
        sa.Column("unaccepted_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skip_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shared_with_groups", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("copied_from_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evolvxsi_workflow_schedule_owner_id", "evolvxsi_workflow_schedule", ["owner_id"])
    op.create_index("ix_evolvxsi_workflow_schedule_next_run_at", "evolvxsi_workflow_schedule", ["next_run_at"])
    op.create_table(
        "evolvxsi_workflow_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evolvxsi_workflow_schedule.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evolvxsi_task.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("route_kind", sa.String(length=20), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_evolvxsi_workflow_run_schedule_id", "evolvxsi_workflow_run", ["schedule_id"])
    op.add_column("evolvxsi_task", sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_evolvxsi_task_schedule", "evolvxsi_task", "evolvxsi_workflow_schedule", ["schedule_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_evolvxsi_task_schedule_id", "evolvxsi_task", ["schedule_id"])


def downgrade() -> None:
    op.drop_index("ix_evolvxsi_task_schedule_id", table_name="evolvxsi_task")
    op.drop_constraint("fk_evolvxsi_task_schedule", "evolvxsi_task", type_="foreignkey")
    op.drop_column("evolvxsi_task", "schedule_id")
    op.drop_index("ix_evolvxsi_workflow_run_schedule_id", table_name="evolvxsi_workflow_run")
    op.drop_table("evolvxsi_workflow_run")
    op.drop_index("ix_evolvxsi_workflow_schedule_next_run_at", table_name="evolvxsi_workflow_schedule")
    op.drop_index("ix_evolvxsi_workflow_schedule_owner_id", table_name="evolvxsi_workflow_schedule")
    op.drop_table("evolvxsi_workflow_schedule")
