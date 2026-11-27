"""Record Company verification on an exact agent release."""

import sqlalchemy as sa
from alembic import op

revision = "287d60eac141"
down_revision = "4bc10a67d2e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_release", sa.Column("verified_at", sa.DateTime(timezone=True)))
    op.add_column("agent_release", sa.Column("verified_by", sa.Uuid()))


def downgrade() -> None:
    op.drop_column("agent_release", "verified_by")
    op.drop_column("agent_release", "verified_at")
