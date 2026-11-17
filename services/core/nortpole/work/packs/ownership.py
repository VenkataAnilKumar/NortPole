"""Who may publish a new version of a pack.

A pack id belongs to the signer of its newest installed version. Before this rule, any trusted signer could install a new
version of another signer's pack and an administrator activating it would hand the pack's users to the new signer's
content. Now a version signed by a different key is refused unless

* the owner's key was revoked (the way a key is rotated: trust the new key, revoke the old, publish), or
* an administrator approved a key change for that pack to that signer (`POST /admin/packs/{id}/transfer`), which lets that
  signer's next version through once and then makes it the owner.

Every refusal and every approval is audited."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.utils.audit import AuditAction, AuditOutcome
from nortpole.work.packs.models import NortPolePackSigner, NortPolePackTransfer, NortPolePackVersion


def owner_of(db: Session, pack_id: str) -> str | None:
    """The signer of the newest installed version, or None when the pack id is new."""
    return db.scalar(select(NortPolePackVersion.signer_key_id).where(NortPolePackVersion.pack_id == pack_id).order_by(NortPolePackVersion.row_id.desc()).limit(1))


def check_publisher(db: Session, pack_id: str, key_id: str) -> None:
    """Raise unless this signer may publish a version of this pack."""
    owner = owner_of(db, pack_id)
    if owner is None or owner == key_id:
        return
    owner_signer = db.get(NortPolePackSigner, owner)
    if owner_signer is None or owner_signer.revoked:
        return
    transfer = db.get(NortPolePackTransfer, pack_id)
    if transfer is not None and transfer.to_key_id == key_id:
        return
    raise NortPoleError(
        NortPoleErrorCode.CONFLICT,
        f"The pack {pack_id} is published by signer {owner}. Signer {key_id} may publish a version of it only after an "
        "administrator approves a key change for this pack, or after the owner's key is revoked.",
    )


def consume(db: Session, pack_id: str, key_id: str) -> None:
    """After a signer publishes with an approved key change, the approval is spent."""
    transfer = db.get(NortPolePackTransfer, pack_id)
    if transfer is not None and transfer.to_key_id == key_id:
        db.delete(transfer)
        db.commit()


def approve_transfer(db: Session, user: User, pack_id: str, to_key_id: str) -> NortPolePackTransfer:
    owner = owner_of(db, pack_id)
    if owner is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "No version of that pack is installed, so it has no owner to change.")
    target = db.get(NortPolePackSigner, to_key_id)
    if target is None or target.revoked:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "The new signer must be a trusted signer that is not revoked.")
    if to_key_id == owner:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "That signer already owns the pack.")
    row = db.get(NortPolePackTransfer, pack_id)
    if row is None:
        row = NortPolePackTransfer(pack_id=pack_id, to_key_id=to_key_id, approved_by_email=user.email)
        db.add(row)
    else:
        row.to_key_id, row.approved_by_email = to_key_id, user.email
    db.commit()
    _audit(user, f"Approved a key change for {pack_id}: {owner} to {to_key_id}", pack_id, AuditOutcome.SUCCESS)
    return row


def cancel_transfer(db: Session, user: User, pack_id: str) -> None:
    row = db.get(NortPolePackTransfer, pack_id)
    if row is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "No key change is approved for that pack.")
    db.delete(row)
    db.commit()
    _audit(user, f"Cancelled the approved key change for {pack_id}", pack_id, AuditOutcome.SUCCESS)


def _audit(user: User, summary: str, pack_id: str, outcome: AuditOutcome) -> None:
    from nortpole.governance.route_policy.audit import record_audit

    record_audit(AuditAction.PACK_OWNER_CHANGE, outcome, actor=user, summary=summary, resource_type="pack", resource_id=pack_id)
