"""product name: NortPole

Built-in skill descriptions seeded by earlier migrations name the product; replace the old name with NortPole so
people see the current name. Only text written by migrations is changed.

Revision ID: b2d4f6a8c0e3
Revises: a1c3e5f7b9d2
Create Date: 2026-11-14 21:00:00.000000

"""

from alembic import op

revision = "b2d4f6a8c0e3"
down_revision = "a1c3e5f7b9d2"
branch_labels = None
depends_on = None

OLD, NEW = "NortPole", "NortPole"


def upgrade() -> None:
    op.execute(
        f"UPDATE skill SET description = replace(description, '{OLD}', '{NEW}') "
        f"WHERE built_in_skill_id IS NOT NULL AND description LIKE '%{OLD}%'"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE skill SET description = replace(description, '{NEW}', '{OLD}') "
        f"WHERE built_in_skill_id IS NOT NULL AND description LIKE '%{NEW}%'"
    )
