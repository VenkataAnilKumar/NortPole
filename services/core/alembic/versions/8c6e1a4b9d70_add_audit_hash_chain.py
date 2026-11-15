"""add the audit hash chain columns

Revision ID: 8c6e1a4b9d70
Revises: 7b5d0f3a8c69
Create Date: 2026-11-13 17:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "8c6e1a4b9d70"
down_revision = "7b5d0f3a8c69"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nortpole_audit_event", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("nortpole_audit_event", sa.Column("row_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_nortpole_audit_event_row_hash", "nortpole_audit_event", ["row_hash"])


def downgrade() -> None:
    op.drop_index("ix_nortpole_audit_event_row_hash", table_name="nortpole_audit_event")
    op.drop_column("nortpole_audit_event", "row_hash")
    op.drop_column("nortpole_audit_event", "prev_hash")
