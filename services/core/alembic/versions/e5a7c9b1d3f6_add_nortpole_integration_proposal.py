"""changes an assistant proposed, waiting for the person's yes

Revision ID: e5a7c9b1d3f6
Revises: c3e5a7b9d1f4
Create Date: 2026-11-17 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5a7c9b1d3f6"
down_revision = "c3e5a7b9d1f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nortpole_integration_proposal",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", sa.String(64), nullable=False),
        sa.Column("integration_version", sa.String(20), nullable=False),
        sa.Column("action_id", sa.String(64), nullable=False),
        sa.Column("summary", sa.String(200), nullable=False),
        sa.Column("arguments", sa.Text(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("outcome", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_nortpole_integration_proposal_user_state", "nortpole_integration_proposal", ["user_id", "state"])


def downgrade() -> None:
    op.drop_index("ix_nortpole_integration_proposal_user_state", table_name="nortpole_integration_proposal")
    op.drop_table("nortpole_integration_proposal")
