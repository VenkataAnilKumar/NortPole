"""Store editable outputs in owned projects."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "1d2db0bbd0aa"
down_revision = "f1b7211cfd5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_output",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("user_project.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_output_project_id", "project_output", ["project_id"])


def downgrade() -> None:
    op.drop_table("project_output")
