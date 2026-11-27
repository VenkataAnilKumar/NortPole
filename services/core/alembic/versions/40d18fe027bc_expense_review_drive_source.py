"""Record the Drive file revision used by scheduled Expense Review."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "40d18fe027bc"
down_revision = "f90728d8f296"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nortpole_workflow_run", sa.Column("drive_source", JSONB(), nullable=True))
    op.create_index("ix_nortpole_workflow_run_chat_session_id", "nortpole_workflow_run", ["chat_session_id"])


def downgrade() -> None:
    op.drop_index("ix_nortpole_workflow_run_chat_session_id", table_name="nortpole_workflow_run")
    op.drop_column("nortpole_workflow_run", "drive_source")
