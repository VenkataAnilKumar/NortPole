"""Resolve optional rules from the currently active, trusted pack."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.enforce import check_route
from nortpole.work.packs.models import (
    NortPolePackEvaluation,
    NortPolePackSigner,
    NortPolePackVersion,
)


def rules_for_document_review(
    db: Session, pack_id: str, model_id: int | None, *, required_version: str | None = None,
) -> tuple[str, str, list[dict]]:
    pack = db.scalar(
        select(NortPolePackVersion)
        .join(NortPolePackSigner, NortPolePackSigner.key_id == NortPolePackVersion.signer_key_id)
        .where(
            NortPolePackVersion.pack_id == pack_id,
            NortPolePackVersion.active.is_(True),
            NortPolePackSigner.revoked.is_(False),
        )
    )
    if pack is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "The selected pack is unavailable.")
    if required_version is not None and pack.version != required_version:
        raise NortPoleError(
            NortPoleErrorCode.CONFLICT,
            "The original pack version is no longer active. Start a new review to use the current rules.",
        )
    route = check_route(db, model_id)
    requirements = pack.manifest["requires"]
    if not route.allowed or route.kind not in requirements["route_kinds"] or route.data_class not in requirements["data_classes"]:
        raise NortPoleError(NortPoleErrorCode.POLICY_BLOCKED, "The selected pack does not support this model route or data class.")
    if pack.manifest.get("evaluation_cases") and not db.scalar(
        select(NortPolePackEvaluation.passed).where(
            NortPolePackEvaluation.pack_id == pack.pack_id,
            NortPolePackEvaluation.version == pack.version,
            NortPolePackEvaluation.model_configuration_id == model_id,
        )
    ):
        raise NortPoleError(NortPoleErrorCode.POLICY_BLOCKED, "The selected pack has not passed its evaluation on this model.")
    return f'{pack.manifest["name"]} ({pack.version})', pack.version, list(pack.manifest.get("review_rules", []))
