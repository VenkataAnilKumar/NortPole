"""Add tested agent versions and pin Chat sessions to a version."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f83e59a0b216"
down_revision = "923c1e6a175b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_release",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("persona_id", sa.Integer(), sa.ForeignKey("persona.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("dependency_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("test_chat_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_response_id", sa.Integer(), nullable=False),
        sa.Column("tested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_by", postgresql.UUID(as_uuid=True)),
        sa.UniqueConstraint("persona_id", "version"),
        sa.UniqueConstraint("persona_id", "test_chat_id"),
    )
    op.create_index(
        "ix_agent_release_active", "agent_release", ["persona_id"], unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.add_column("persona", sa.Column("agent_release_draft", postgresql.JSONB()))
    op.add_column("chat_session", sa.Column("agent_preview_fingerprint", sa.String(length=64)))
    op.add_column("chat_session", sa.Column("agent_release_id", sa.Integer()))
    op.create_foreign_key("fk_chat_session_agent_release", "chat_session", "agent_release", ["agent_release_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_chat_session_agent_release", "chat_session", type_="foreignkey")
    op.drop_column("chat_session", "agent_release_id")
    op.drop_column("chat_session", "agent_preview_fingerprint")
    op.drop_column("persona", "agent_release_draft")
    op.drop_table("agent_release")
