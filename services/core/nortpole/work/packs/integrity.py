"""Re-check stored pack versions against what was signed.

Each version keeps the exact canonical JSON its signer signed (``signed_manifest``). A check confirms, from the
database alone, that:

* those bytes hash to the stored digest;
* the stored signature over those bytes verifies with the signer's registered public key;
* the signed manifest names the same pack id and version as the row;
* the copy the product reads (``manifest``, defaults filled in) is the signed manifest with defaults filled in, so
  nobody changed what people are offered without changing what was signed.

What it does NOT detect: someone who can write the database and also replaces a signer's public key, or a version
installed before signed bytes were kept whose bytes could not be recovered (reported as ``unverifiable``)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from nortpole.work.packs.manifest import Manifest
from nortpole.work.packs.models import NortPolePackSigner, NortPolePackVersion
from nortpole.work.packs.signing import SignatureProblem, verify


class VersionCheck(BaseModel):
    pack_id: str
    version: str
    # "verified", "failed" or "unverifiable" (installed before signed bytes were kept, and not recovered).
    status: str
    signer_key_id: str
    signer_revoked: bool = False
    problems: list[str] = []


class IntegrityReport(BaseModel):
    # True when every version verified, False when any failed, None when none failed but some could not be checked.
    ok: bool | None
    checked: int
    verified: int
    failed: int
    unverifiable: int
    versions: list[VersionCheck]


def _normalized(manifest: dict[str, Any]) -> dict[str, Any]:
    return Manifest.model_validate(manifest).model_dump(mode="json")


def check_version(row: NortPolePackVersion, signer: NortPolePackSigner | None) -> VersionCheck:
    out = VersionCheck(pack_id=row.pack_id, version=row.version, status="verified", signer_key_id=row.signer_key_id,
                       signer_revoked=signer is None or signer.revoked)
    if row.signed_manifest is None:
        out.status = "unverifiable"
        out.problems.append("Installed before the signed bytes were kept, and they could not be recovered. "
                            "Upload the same signed package again, or install a new version.")
        return out
    raw = row.signed_manifest.encode("utf-8")
    if hashlib.sha256(raw).hexdigest() != row.digest:
        out.problems.append("The signed manifest does not hash to the stored digest.")
    if signer is None:
        out.problems.append(f"The signer {row.signer_key_id} is not registered, so the signature cannot be checked.")
    else:
        try:
            verify(signer.public_key, row.signature, raw)
        except SignatureProblem as e:
            out.problems.append(f"Signature: {e}")
    try:
        signed = json.loads(raw)
    except ValueError:
        out.problems.append("The signed manifest is not valid JSON.")
        signed = None
    if isinstance(signed, dict):
        if signed.get("id") != row.pack_id or signed.get("version") != row.version:
            out.problems.append("The signed manifest names a different pack id or version than the stored row.")
        try:
            if _normalized(signed) != _normalized(row.manifest):
                out.problems.append("The stored manifest people are offered differs from the signed manifest.")
        except ValidationError:
            out.problems.append("The stored or signed manifest is no longer valid.")
    elif signed is not None:
        out.problems.append("The signed manifest is not a JSON object.")
    if out.problems:
        out.status = "failed"
    return out


def check_all(db: Session) -> IntegrityReport:
    signers = {s.key_id: s for s in db.scalars(select(NortPolePackSigner))}
    rows = db.scalars(select(NortPolePackVersion).order_by(NortPolePackVersion.pack_id, NortPolePackVersion.row_id))
    checks = [check_version(v, signers.get(v.signer_key_id)) for v in rows]
    n = {s: sum(c.status == s for c in checks) for s in ("verified", "failed", "unverifiable")}
    ok = False if n["failed"] else (None if n["unverifiable"] else True)
    return IntegrityReport(ok=ok, checked=len(checks), verified=n["verified"], failed=n["failed"],
                           unverifiable=n["unverifiable"], versions=checks)
