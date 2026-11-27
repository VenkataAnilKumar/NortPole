"""Add per-schedule Inbox preferences for workflow results."""

import sqlalchemy as sa
from alembic import op

revision = "98a32cfe9d70"
down_revision = "40d18fe027bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, default in (
        ("notify_needs_review", sa.true()),
        ("notify_run_failed", sa.true()),
        ("notify_run_complete", sa.false()),
    ):
        op.add_column(
            "nortpole_workflow_schedule",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=default),
        )


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM notification WHERE notif_type IN "
        "('WORKFLOW_RUN_NEEDS_REVIEW', 'WORKFLOW_RUN_FAILED', 'WORKFLOW_RUN_COMPLETE')"
    ))
    for name in ("notify_run_complete", "notify_run_failed", "notify_needs_review"):
        op.drop_column("nortpole_workflow_schedule", name)
