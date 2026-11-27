"""Add workspace project membership."""

import sqlalchemy as sa
from alembic import op

revision = "813b39e755ad"
down_revision = "ca2c7423ab98"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_member",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("user_project.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(6), nullable=False),
        sa.CheckConstraint("role in ('viewer', 'editor')", name="project_member_role"),
    )
    op.create_index("ix_project_member_user_id", "project_member", ["user_id"])


def downgrade() -> None:
    op.drop_table("project_member")
