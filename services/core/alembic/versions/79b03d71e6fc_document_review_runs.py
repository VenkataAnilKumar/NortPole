"""Store Document Review outcomes with the originating Chat responses."""

import sqlalchemy as sa
from alembic import op

revision = "79b03d71e6fc"
down_revision = "98a32cfe9d70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_message", sa.Column("document_review_needs_review", sa.Boolean(), nullable=True))
    op.create_index(
        "ix_chat_message_document_review_runs", "chat_message", ["id"],
        postgresql_where=sa.text("document_review_needs_review IS NOT NULL"),
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM notification WHERE notif_type = 'DOCUMENT_REVIEW_NEEDS_REVIEW'"))
    op.drop_index("ix_chat_message_document_review_runs", table_name="chat_message")
    op.drop_column("chat_message", "document_review_needs_review")
