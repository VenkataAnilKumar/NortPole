"""add approval and export fields to evolvxsi_task

Approval is bound to one exact draft by its fingerprint; export is a separate
step with a fresh access check.

Revision ID: e81b6c2d4a93
Revises: d7f3a1c05b12
Create Date: 2026-11-12 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "e81b6c2d4a93"
down_revision = "d7f3a1c05b12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evolvxsi_task", sa.Column("draft_hash", sa.String(length=64), nullable=True))
    op.add_column("evolvxsi_task", sa.Column("approved_hash", sa.String(length=64), nullable=True))
    op.add_column("evolvxsi_task", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("evolvxsi_task", sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for c in ("exported_at", "approved_at", "approved_hash", "draft_hash"):
        op.drop_column("evolvxsi_task", c)
