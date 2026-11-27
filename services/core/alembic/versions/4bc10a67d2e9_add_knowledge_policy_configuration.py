"""Store source-bound policy rules on Knowledge libraries."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "4bc10a67d2e9"
down_revision = "f83e59a0b216"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_set", sa.Column("policy_configuration", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_set", "policy_configuration")
