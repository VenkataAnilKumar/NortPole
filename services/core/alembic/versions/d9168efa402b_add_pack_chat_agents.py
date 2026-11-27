"""Associate a user's Chat agent with a stable pack agent identity."""

import sqlalchemy as sa
from alembic import op

revision = "d9168efa402b"
down_revision = "287d60eac141"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persona", sa.Column("chat_pack_id", sa.String(64)))
    op.add_column("persona", sa.Column("chat_pack_agent_id", sa.String(64)))
    op.create_unique_constraint(
        "uq_persona_owned_pack_chat_agent", "persona",
        ["user_id", "chat_pack_id", "chat_pack_agent_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_persona_owned_pack_chat_agent", "persona", type_="unique")
    op.drop_column("persona", "chat_pack_agent_id")
    op.drop_column("persona", "chat_pack_id")
