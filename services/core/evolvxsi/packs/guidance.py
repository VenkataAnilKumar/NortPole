"""The house style a pack's template asks for, read from the exact pack version a
task started from (not the version that is active now)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from evolvxsi.packs.models import EvolvXSIPackVersion


def style_for(db: Session, pack_id: str | None, version: str | None, template_id: str | None) -> str:
    if not (pack_id and version and template_id):
        return ""
    v = db.scalar(select(EvolvXSIPackVersion).where(EvolvXSIPackVersion.pack_id == pack_id, EvolvXSIPackVersion.version == version))
    if v is None:
        return ""
    t = next((t for t in v.manifest.get("templates", []) if t.get("id") == template_id), None)
    return (t or {}).get("style", "") or ""
