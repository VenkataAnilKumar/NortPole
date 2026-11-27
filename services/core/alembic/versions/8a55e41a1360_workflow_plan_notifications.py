"""Add an in-app plan notification preference to workflow schedules."""

import sqlalchemy as sa
from alembic import op

revision = "8a55e41a1360"
down_revision = "f6b8d0e2a4c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "nortpole_workflow_schedule",
        sa.Column("notify_plan_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("nortpole_workflow_schedule", "notify_plan_ready")
