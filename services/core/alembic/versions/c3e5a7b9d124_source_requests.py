"""requests from the Discover page (connectors, skills, plugins)

Revision ID: c3e5a7b9d124
Revises: b2d4f6a8c013
Create Date: 2026-11-14 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3e5a7b9d124"
down_revision = "b2d4f6a8c013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evolvxsi_source_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("item_key", sa.String(length=120), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_by_email", sa.String(), nullable=False),
        sa.Column("decided_by_email", sa.String(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_evolvxsi_source_request_state", "evolvxsi_source_request", ["state"])
    op.create_index("ix_evolvxsi_source_request_requester", "evolvxsi_source_request", ["requested_by_id"])


def downgrade() -> None:
    op.drop_index("ix_evolvxsi_source_request_requester", table_name="evolvxsi_source_request")
    op.drop_index("ix_evolvxsi_source_request_state", table_name="evolvxsi_source_request")
    op.drop_table("evolvxsi_source_request")
