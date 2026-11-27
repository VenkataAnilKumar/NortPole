"""Persist whether an explicit Expense Review response needs clarification."""

import sqlalchemy as sa
from alembic import op

revision = "22ba56dccaf0"
down_revision = "8a55e41a1360"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_message", sa.Column("receipt_review_needs_review", sa.Boolean(), nullable=True))
    op.create_index(
        "ix_chat_message_expense_review_runs",
        "chat_message",
        ["id"],
        postgresql_where=sa.text("receipt_review_needs_review IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_chat_message_expense_review_runs", table_name="chat_message")
    op.drop_column("chat_message", "receipt_review_needs_review")
