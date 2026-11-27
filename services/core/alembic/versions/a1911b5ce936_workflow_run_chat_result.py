"""Record the exact Chat response reserved for a scheduled review."""

import sqlalchemy as sa
from alembic import op

revision = "a1911b5ce936"
down_revision = "cbc933e52879"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nortpole_workflow_run", sa.Column("chat_result_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_workflow_run_chat_result", "nortpole_workflow_run", "chat_message",
        ["chat_result_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_workflow_run_chat_result", "nortpole_workflow_run", type_="foreignkey")
    op.drop_column("nortpole_workflow_run", "chat_result_id")
