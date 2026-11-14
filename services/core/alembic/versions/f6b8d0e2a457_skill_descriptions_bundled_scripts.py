"""built-in company-search and image-generation skills use bundled scripts

Both skills used an external command-line tool that the sandbox no longer installs; they now ship their
own scripts (``company_search.py``, ``image_gen.py``). This updates the descriptions people see.

Revision ID: f6b8d0e2a457
Revises: e5a7c9d1f346
Create Date: 2026-11-14 20:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "f6b8d0e2a457"
down_revision = "e5a7c9d1f346"
branch_labels = None
depends_on = None

_DESCRIPTIONS = {
    "company-search": (
        "Search company knowledge with the bundled company_search.py script. Returns permissioned, "
        "citation-rich results from connected sources."
    ),
    "image-generation": (
        "Generate or edit images with the bundled image_gen.py script, using the image generation "
        "provider configured in EvolvXSI."
    ),
}

_OLD_DESCRIPTIONS = {
    "company-search": (
        "Search company knowledge using evolvxsi-cli. Returns permissioned, "
        "citation-rich results from connected sources."
    ),
    "image-generation": (
        "Generate or edit images with evolvxsi-cli using the image generation provider "
        "configured in EvolvXSI."
    ),
}

_skill_table = sa.table(
    "skill",
    sa.column("description", sa.Text),
    sa.column("built_in_skill_id", sa.String),
)


def _set(descriptions: dict[str, str]) -> None:
    bind = op.get_bind()
    for skill_id, description in descriptions.items():
        bind.execute(
            sa.update(_skill_table)
            .where(_skill_table.c.built_in_skill_id == skill_id)
            .values(description=description)
        )


def upgrade() -> None:
    _set(_DESCRIPTIONS)


def downgrade() -> None:
    _set(_OLD_DESCRIPTIONS)
