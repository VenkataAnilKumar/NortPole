"""remove the built-in craft-documentation skill

The skill sent the agent to the inherited product's public documentation site, which does not describe
EvolvXSI. Its definition is gone from the built-in registry; this removes the seeded row too.

Revision ID: e5a7c9d1f346
Revises: d4f6b8c0e235
Create Date: 2026-11-14 18:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "e5a7c9d1f346"
down_revision = "d4f6b8c0e235"
branch_labels = None
depends_on = None

_skill_table = sa.table("skill", sa.column("built_in_skill_id", sa.String))


def upgrade() -> None:
    op.get_bind().execute(
        sa.delete(_skill_table).where(
            _skill_table.c.built_in_skill_id == "craft-documentation"
        )
    )


def downgrade() -> None:
    # Not restored: the skill's definition no longer exists, so a restored row would be hidden anyway.
    pass
