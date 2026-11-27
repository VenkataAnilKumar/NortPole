"""Store Chat workflow schedule proposals and their confirmation state."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "b34fa348195d"
down_revision = "1d2db0bbd0aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nortpole_workflow_schedule_proposal",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("owner_id", UUID(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chat_id", UUID(), sa.ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_message.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(10), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("preview", JSONB(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("message_id", "fingerprint", name="uq_workflow_proposal_message"),
    )
    op.create_index("ix_workflow_proposal_chat", "nortpole_workflow_schedule_proposal", ["chat_id", "created_at"])
    op.create_index("ix_workflow_proposal_queue", "nortpole_workflow_schedule_proposal", ["state", "created_at"])


def downgrade() -> None:
    op.drop_table("nortpole_workflow_schedule_proposal")
