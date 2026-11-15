"""add nortpole_audit_event

A queryable record of policy changes and blocked model requests. Rows hold no
message content, only who, what, when and the policy facts behind a decision.

Revision ID: 9b1e7c3a5d20
Revises: fdaeeca238a1
Create Date: 2026-11-10 23:55:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9b1e7c3a5d20"
down_revision = "fdaeeca238a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nortpole_audit_event",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("actor_email", sa.String(), nullable=True),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "ix_nortpole_audit_event_created_at", "nortpole_audit_event", ["created_at"]
    )
    op.create_index(
        "ix_nortpole_audit_event_action", "nortpole_audit_event", ["action"]
    )


def downgrade() -> None:
    op.drop_index("ix_nortpole_audit_event_action", table_name="nortpole_audit_event")
    op.drop_index("ix_nortpole_audit_event_created_at", table_name="nortpole_audit_event")
    op.drop_table("nortpole_audit_event")
