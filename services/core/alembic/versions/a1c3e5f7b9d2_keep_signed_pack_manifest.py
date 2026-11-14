"""keep the exact signed bytes of each pack version

A pack version stored only the manifest with defaults filled in, which is not what was signed, so neither its digest
nor its signature could be re-checked from the database. ``signed_manifest`` now keeps the exact canonical JSON that
was signed. For rows installed before this, the original bytes are gone; they are recovered only where the stored
copy hashes to the stored digest (the uploaded manifest already had every default written out). The rest stay null:
they are reported as not verifiable until the same signed package is uploaded again or a new version is installed.

Revision ID: a1c3e5f7b9d2
Revises: f6b8d0e2a457
Create Date: 2026-11-14 22:00:00.000000

"""

import hashlib
import json

import sqlalchemy as sa

from alembic import op

revision = "a1c3e5f7b9d2"
down_revision = "f6b8d0e2a457"
branch_labels = None
depends_on = None


def _canonical(manifest: dict) -> str:
    # Same as nortpole.work.packs.manifest.canonical_bytes; written out so the migration does not move with app code.
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def upgrade() -> None:
    op.add_column("evolvxsi_pack_version", sa.Column("signed_manifest", sa.Text(), nullable=True))
    conn = op.get_bind()
    rows = conn.execute(sa.text("select row_id, manifest, digest from evolvxsi_pack_version")).fetchall()
    for row_id, manifest, digest in rows:
        text = _canonical(manifest)
        if hashlib.sha256(text.encode("utf-8")).hexdigest() == digest:
            conn.execute(sa.text("update evolvxsi_pack_version set signed_manifest = :t where row_id = :r"), {"t": text, "r": row_id})


def downgrade() -> None:
    op.drop_column("evolvxsi_pack_version", "signed_manifest")
