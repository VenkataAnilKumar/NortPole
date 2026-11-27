"""Retain the provenance of Search evidence used in a chat response."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "b320a817df43"
down_revision = "813b39e755ad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_message", sa.Column("search_evidence_provenance", JSONB()))


def downgrade() -> None:
    op.drop_column("chat_message", "search_evidence_provenance")
