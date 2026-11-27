"""Retain structured review findings and an append-only decision history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "f1b7211cfd5e"
down_revision = "79b03d71e6fc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_message", sa.Column("document_review_report", JSONB(), nullable=True))
    op.create_table(
        "document_review_decision",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_message.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_number", sa.Integer(), nullable=False),
        sa.Column("actor_id", UUID(), sa.ForeignKey("user.id", ondelete="SET NULL")),
        sa.Column("request_id", UUID(), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("message_id", "request_id", name="uq_document_review_decision_request"),
        sa.CheckConstraint("finding_number > 0", name="ck_document_review_decision_finding"),
        sa.CheckConstraint(
            "action IN ('revision_requested', 'exception_accepted', 'resolved')",
            name="ck_document_review_decision_action",
        ),
    )
    op.create_index("ix_document_review_decision_finding", "document_review_decision", ["message_id", "finding_number", "id"])


def downgrade() -> None:
    op.execute(sa.text(
        "UPDATE notification SET additional_data = jsonb_set(additional_data, '{link}', "
        "to_jsonb('/app?chatId=' || (additional_data->>'chat_session_id'))) "
        "WHERE notif_type = 'DOCUMENT_REVIEW_NEEDS_REVIEW' AND additional_data ? 'chat_session_id'"
    ))
    op.drop_table("document_review_decision")
    op.drop_column("chat_message", "document_review_report")
