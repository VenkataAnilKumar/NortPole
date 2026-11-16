"""a person's use of an integration: installed, their settings and their own sealed account

Revision ID: c3e5a7b9d1f4
Revises: b2d4f6a8c0e3
Create Date: 2026-11-16 20:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3e5a7b9d1f4"
down_revision = "b2d4f6a8c0e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nortpole_integration_use",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", sa.String(64), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("credential", sa.Text(), nullable=True),
        sa.Column("installed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "integration_id", name="uq_nortpole_integration_use"),
    )
    op.create_index("ix_nortpole_integration_use_user_id", "nortpole_integration_use", ["user_id"])
    op.create_index("ix_nortpole_integration_use_integration_id", "nortpole_integration_use", ["integration_id"])


def downgrade() -> None:
    op.drop_index("ix_nortpole_integration_use_integration_id", table_name="nortpole_integration_use")
    op.drop_index("ix_nortpole_integration_use_user_id", table_name="nortpole_integration_use")
    op.drop_table("nortpole_integration_use")
