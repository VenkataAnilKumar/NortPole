"""Link a retry attempt to the run it replaces."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "cbc933e52879"
down_revision = "31ad488b2cb4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nortpole_workflow_run", sa.Column("retry_of_id", UUID(), nullable=True))
    op.create_foreign_key(
        "fk_workflow_run_retry_of", "nortpole_workflow_run", "nortpole_workflow_run",
        ["retry_of_id"], ["id"], ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_workflow_run_retry_of", "nortpole_workflow_run", ["retry_of_id"])


def downgrade() -> None:
    op.drop_constraint("uq_workflow_run_retry_of", "nortpole_workflow_run", type_="unique")
    op.drop_constraint("fk_workflow_run_retry_of", "nortpole_workflow_run", type_="foreignkey")
    op.drop_column("nortpole_workflow_run", "retry_of_id")
