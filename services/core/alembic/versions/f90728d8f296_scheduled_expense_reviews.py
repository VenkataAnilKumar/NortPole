"""Store Expense Review inputs and link scheduled runs to their chat."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "f90728d8f296"
down_revision = "22ba56dccaf0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nortpole_workflow_schedule", sa.Column("expense_review", JSONB(), nullable=True))
    op.add_column("nortpole_workflow_run", sa.Column("chat_session_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_workflow_run_chat_session",
        "nortpole_workflow_run", "chat_session",
        ["chat_session_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_workflow_run_chat_session", "nortpole_workflow_run", type_="foreignkey")
    op.drop_column("nortpole_workflow_run", "chat_session_id")
    op.drop_column("nortpole_workflow_schedule", "expense_review")
