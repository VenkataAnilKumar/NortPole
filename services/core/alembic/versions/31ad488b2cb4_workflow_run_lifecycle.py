"""Persist workflow run origin and lifecycle before execution."""

import sqlalchemy as sa
from alembic import op

revision = "31ad488b2cb4"
down_revision = "b34fa348195d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nortpole_workflow_run", sa.Column("trigger", sa.String(16)))
    op.add_column("nortpole_workflow_run", sa.Column("schedule_version", sa.Integer()))
    op.add_column("nortpole_workflow_run", sa.Column("started_at", sa.DateTime(timezone=True)))
    op.add_column("nortpole_workflow_run", sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_workflow_run_queued", "nortpole_workflow_run", ["fired_at"],
        postgresql_where=sa.text("outcome = 'queued' AND trigger = 'timer'"),
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_run_queued", table_name="nortpole_workflow_run")
    for field in ("completed_at", "started_at", "schedule_version", "trigger"):
        op.drop_column("nortpole_workflow_run", field)
