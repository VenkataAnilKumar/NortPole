"""How far an action may go. Three tiers, lowest first:

* read_only         - nothing can be proposed to the destination.
* draft_only        - the exact content can be prepared and reviewed, but it cannot be
                      approved or sent from the product.
* act_with_approval - prepare, approve the exact content, send (the default).

The effective tier is the lower of the destination's tier and, for a task started
from a pack, the pack version's `autonomy`. Both are re-read at every step, so a tier
lowered after a proposal still stops the send."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from evolvxsi.work.packs.models import EvolvXSIPackVersion

TIERS = ("read_only", "draft_only", "act_with_approval")
_RANK = {t: i for i, t in enumerate(TIERS)}
LABEL = {
    "read_only": "read-only (nothing can be proposed)",
    "draft_only": "draft-only (the content can be prepared but not approved or sent)",
    "act_with_approval": "act with approval",
}


def lowest(*tiers: str) -> str:
    known = [t for t in tiers if t in _RANK]
    return min(known, key=_RANK.__getitem__) if known else "read_only"  # an unknown value fails closed


def pack_autonomy(db: Session, pack_id: str | None, version: str | None) -> str:
    if not (pack_id and version):
        return "act_with_approval"
    v = db.scalar(select(EvolvXSIPackVersion).where(EvolvXSIPackVersion.pack_id == pack_id, EvolvXSIPackVersion.version == version))
    if v is None:
        return "read_only"  # the pack version the task started from is gone: fail closed
    return v.manifest.get("autonomy") or "act_with_approval"


def effective_tier(db: Session, target_tier: str | None, pack_id: str | None, version: str | None) -> str:
    return lowest(target_tier or "act_with_approval", pack_autonomy(db, pack_id, version))


def at_least(tier: str, needed: str) -> bool:
    return _RANK.get(tier, -1) >= _RANK[needed]
