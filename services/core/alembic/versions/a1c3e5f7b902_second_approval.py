"""second approval for sends

Revision ID: a1c3e5f7b902
Revises: 9d7f2b5c0a81
Create Date: 2026-11-13 22:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a1c3e5f7b902"
down_revision = "9d7f2b5c0a81"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evolvxsi_action_target", sa.Column("require_second_approval", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("evolvxsi_action", sa.Column("second_approver_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("evolvxsi_action", sa.Column("second_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_evolvxsi_action_second_approver", "evolvxsi_action", "user", ["second_approver_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_evolvxsi_action_second_approver", "evolvxsi_action", type_="foreignkey")
    op.drop_column("evolvxsi_action", "second_approved_at")
    op.drop_column("evolvxsi_action", "second_approver_id")
    op.drop_column("evolvxsi_action_target", "require_second_approval")
