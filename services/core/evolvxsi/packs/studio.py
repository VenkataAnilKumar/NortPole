"""Studio: administrators write a pack (workflows, guides, an agent) in the product instead of signing one outside.

A Studio pack goes through the same path as any pack: the strict manifest check, a signature, installation as an
inactive version, the reviewer's reading of its guides and agents, evaluation if it has cases, and activation. It is
signed by a workspace key that the product creates on first use and registers as a trusted signer ("workspace-studio").
That key lives in this product's database, so a Studio pack proves only that an administrator of this workspace
published it, not that it came from a pack author outside. Revoking the signer stops every Studio pack at once."""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.key_value_store.factory import get_kv_store
from evolvxsi.key_value_store.interface import KvKeyNotFoundError
from evolvxsi.packs.manifest import Manifest, canonical_bytes
from evolvxsi.packs.models import EvolvXSIPackSigner, EvolvXSIPackVersion

router = APIRouter(prefix="/admin/studio")
KEY_KV = "evolvxsi_studio_signer"
DRAFTS_KV = "evolvxsi_studio_drafts"
KEY_ID = "workspace-studio"
MAX_DRAFTS = 50


class Problem(BaseModel):
    where: str
    message: str


class CheckResult(BaseModel):
    ok: bool
    problems: list[Problem]


class Draft(BaseModel):
    manifest: dict


def _kv_load(key: str, default):  # type: ignore[no-untyped-def]
    try:
        return get_kv_store().load(key)
    except KvKeyNotFoundError:
        return default


def check(manifest: dict) -> CheckResult:
    """The same strict check an installed pack gets, with every problem listed for the editor."""
    try:
        Manifest.model_validate(manifest)
        return CheckResult(ok=True, problems=[])
    except ValidationError as e:
        return CheckResult(ok=False, problems=[Problem(where=".".join(str(x) for x in err["loc"]) or "pack",
                                                       message=str(err["msg"]).removeprefix("Value error, ")) for err in e.errors()[:20]])


def _signing_key(db: Session, user: User) -> Ed25519PrivateKey:
    """The workspace key, created and trusted on first use. Refused if an administrator revoked it."""
    stored = _kv_load(KEY_KV, None)
    signer = db.get(EvolvXSIPackSigner, KEY_ID)
    if stored is None:
        if signer is not None:
            raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "A signer named workspace-studio exists but its key is not stored here.")
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        get_kv_store().store(KEY_KV, {"key_id": KEY_ID, "private_key": base64.b64encode(raw).decode()})
        from evolvxsi.packs.api import SignerIn, add_signer

        add_signer(SignerIn(key_id=KEY_ID, public_key=base64.b64encode(pub).decode(), label="Studio (this workspace)"), user=user, db_session=db)
        return key
    if signer is not None and signer.revoked:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "The Studio signer was revoked, so Studio packs cannot be published.")
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(stored["private_key"]))


@router.get("")
def list_drafts(_: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> dict[str, dict]:
    return _kv_load(DRAFTS_KV, {})


@router.post("/check")
def check_draft(body: Draft, _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> CheckResult:
    return check(body.manifest)


@router.put("/{pack_id}")
def save_draft(pack_id: str, body: Draft, _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> CheckResult:
    """Save a draft as it is, even with problems, and say what they are. Nothing is installed."""
    if body.manifest.get("id") != pack_id:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "The draft's id must match the address it is saved under.")
    if len(canonical_bytes(body.manifest)) > 256_000:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "The draft is too large.")
    drafts = _kv_load(DRAFTS_KV, {})
    if pack_id not in drafts and len(drafts) >= MAX_DRAFTS:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Too many drafts. Delete some first.")
    drafts[pack_id] = body.manifest
    get_kv_store().store(DRAFTS_KV, drafts)
    return check(body.manifest)


@router.delete("/{pack_id}")
def delete_draft(pack_id: str, _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))) -> dict[str, dict]:
    drafts = _kv_load(DRAFTS_KV, {})
    drafts.pop(pack_id, None)
    get_kv_store().store(DRAFTS_KV, drafts)
    return drafts


@router.post("/{pack_id}/publish")
def publish(
    pack_id: str,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
):  # type: ignore[no-untyped-def]
    """Sign the saved draft with the workspace key and install it as an inactive version (the usual install path,
    audited). A pack id that another signer already publishes cannot be taken over from here."""
    from evolvxsi.packs.api import Package, install_pack

    manifest = _kv_load(DRAFTS_KV, {}).get(pack_id)
    if manifest is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "No saved draft with that id.")
    result = check(manifest)
    if not result.ok:
        first = result.problems[0]
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, f"The draft has problems; the first is at {first.where}: {first.message}")
    others = db_session.scalars(select(EvolvXSIPackVersion.signer_key_id).where(
        EvolvXSIPackVersion.pack_id == pack_id, EvolvXSIPackVersion.signer_key_id != KEY_ID)).first()
    if others:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, f"The pack id {pack_id} is published by another signer ({others}). Use a different id.")
    key = _signing_key(db_session, user)
    sig = base64.b64encode(key.sign(canonical_bytes(manifest))).decode()
    return install_pack(Package(manifest=manifest, key_id=KEY_ID, signature=sig), user=user, db_session=db_session)
