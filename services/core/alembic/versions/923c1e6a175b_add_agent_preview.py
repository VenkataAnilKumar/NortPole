"""Store private agent preview configuration on the test chat."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "923c1e6a175b"
down_revision = "b320a817df43"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_session", sa.Column("agent_preview", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("chat_session", "agent_preview")
