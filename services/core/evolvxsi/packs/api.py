"""Pack endpoints. Administrators register trusted signers, install signed
packages and choose the active version (an upgrade or a rollback). People see
the active packs and start a draft task from a template."""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.packs.manifest import Manifest, canonical_bytes, digest, version_key
from evolvxsi.packs.evaluation import evaluate
from evolvxsi.packs.models import EvolvXSIPackEvaluation, EvolvXSIPackSigner, EvolvXSIPackVersion
from evolvxsi.packs.signing import SignatureProblem, parse_public_key, verify
from evolvxsi.route_policy.audit import record_audit
from evolvxsi.tasks.api import TaskView, _view
from evolvxsi.tasks.models import EvolvXSITask
from evolvxsi.tasks.states import TaskState
from evolvxsi.utils.audit import AuditAction, AuditOutcome

router = APIRouter()
MAX_PACKAGE_BYTES = 256 * 1024


class SignerIn(BaseModel):
    key_id: str
    public_key: str
    label: str = ""


class SignerView(BaseModel):
    key_id: str
    label: str
    revoked: bool


class Package(BaseModel):
    manifest: dict
    signature: str
    key_id: str


class EvalView(BaseModel):
    model_name: str
    route_kind: str
    passed: bool
    cases_passed: int
    cases_total: int
    run_at: datetime.datetime
    failures: list[str]


class VersionView(BaseModel):
    pack_id: str
    version: str
    name: str
    vertical: str
    active: bool
    signer_key_id: str
    signer_revoked: bool
    digest: str
    installed_at: datetime.datetime
    evaluation_cases: int = 0
    evaluations: list[EvalView] = []


class TemplateView(BaseModel):
    id: str
    title: str
    request: str
    desired_output: str


class PackView(BaseModel):
    pack_id: str
    version: str
    name: str
    vertical: str
    description: str
    templates: list[TemplateView]
    data_classes: list[str]
    route_kinds: list[str]
    requests_send_destinations: bool
    # False when the pack has evaluation cases and has not passed them on the
    # model route in use now; starting a task from it would be refused.
    ready_on_current_route: bool = True
    readiness_note: str | None = None


def _audit(user: User, action: AuditAction, summary: str, rid: str, outcome: AuditOutcome = AuditOutcome.SUCCESS) -> None:
    record_audit(action, outcome, actor=user, summary=summary, resource_type="pack", resource_id=rid)


def _revoked(db: Session, key_id: str) -> bool:
    signer = db.get(EvolvXSIPackSigner, key_id)
    return signer is None or signer.revoked


def _evals(db: Session, pack_id: str, version: str) -> list[EvalView]:
    rows = db.scalars(select(EvolvXSIPackEvaluation).where(
        EvolvXSIPackEvaluation.pack_id == pack_id, EvolvXSIPackEvaluation.version == version).order_by(EvolvXSIPackEvaluation.run_at.desc()))
    return [EvalView(model_name=e.model_name, route_kind=e.route_kind, passed=e.passed, cases_passed=e.cases_passed,
                     cases_total=e.cases_total, run_at=e.run_at,
                     failures=[d["question"] + ": " + d["reason"] for d in e.details if not d["passed"]]) for e in rows]


def _vview(db: Session, v: EvolvXSIPackVersion) -> VersionView:
    m = v.manifest
    return VersionView(
        pack_id=v.pack_id, version=v.version, name=m["name"], vertical=m["vertical"], active=v.active,
        signer_key_id=v.signer_key_id, signer_revoked=_revoked(db, v.signer_key_id), digest=v.digest, installed_at=v.installed_at,
        evaluation_cases=len(m.get("evaluation_cases", [])), evaluations=_evals(db, v.pack_id, v.version),
    )


def current_model(db: Session):  # type: ignore[no-untyped-def]
    from evolvxsi.db.enums import LLMModelFlowType
    from evolvxsi.db.llm import fetch_default_model

    return fetch_default_model(db, LLMModelFlowType.CHAT)


def passed_on_current_model(db: Session, pack_id: str, version: str, manifest: dict) -> tuple[bool, str | None]:
    """A pack with no evaluation cases needs no evaluation. One with cases must
    have passed them, at this exact version, on the model in use now."""
    if not manifest.get("evaluation_cases"):
        return True, None
    model = current_model(db)
    if model is None:
        return False, "there is no default model"
    ev = db.scalar(select(EvolvXSIPackEvaluation).where(
        EvolvXSIPackEvaluation.pack_id == pack_id, EvolvXSIPackEvaluation.version == version,
        EvolvXSIPackEvaluation.model_configuration_id == model.id))
    if ev is None:
        return False, f"it has not been evaluated on {model.name}"
    if not ev.passed:
        return False, f"it did not pass evaluation on {model.name} ({ev.cases_passed} of {ev.cases_total} cases)"
    return True, None


# ---- administrators ----------------------------------------------------------

@router.get("/admin/pack-signers")
def list_signers(
    _: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> list[SignerView]:
    return [SignerView(key_id=s.key_id, label=s.label, revoked=s.revoked)
            for s in db_session.scalars(select(EvolvXSIPackSigner).order_by(EvolvXSIPackSigner.key_id))]


@router.post("/admin/pack-signers")
def add_signer(
    body: SignerIn,
    user: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> SignerView:
    try:
        parse_public_key(body.public_key)
    except SignatureProblem as e:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, str(e)) from e
    if not body.key_id.strip() or len(body.key_id) > 80:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "A signer needs a key id of at most 80 characters.")
    if db_session.get(EvolvXSIPackSigner, body.key_id):
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "A signer with that key id already exists.")
    db_session.add(EvolvXSIPackSigner(key_id=body.key_id, public_key=body.public_key, label=body.label[:200]))
    db_session.commit()
    _audit(user, AuditAction.PACK_SIGNER_CHANGE, f"Trusted pack signer {body.key_id}", body.key_id)
    return SignerView(key_id=body.key_id, label=body.label, revoked=False)


@router.post("/admin/pack-signers/{key_id}/revoke")
def revoke_signer(
    key_id: str,
    user: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> SignerView:
    s = db_session.get(EvolvXSIPackSigner, key_id)
    if s is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Signer not found.")
    s.revoked = True
    db_session.commit()
    _audit(user, AuditAction.PACK_SIGNER_CHANGE, f"Revoked pack signer {key_id}; its packs stop being offered", key_id)
    return SignerView(key_id=s.key_id, label=s.label, revoked=True)


@router.get("/admin/packs")
def list_versions(
    _: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> list[VersionView]:
    rows = db_session.scalars(select(EvolvXSIPackVersion).order_by(EvolvXSIPackVersion.pack_id, EvolvXSIPackVersion.row_id.desc()))
    return [_vview(db_session, v) for v in rows]


@router.post("/admin/packs")
def install_pack(
    pkg: Package,
    user: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> VersionView:
    """Install a signed package (inactive until activated). Refused when the
    signer is unknown or revoked, the signature does not match the exact
    manifest, or the manifest is invalid; the reason is stated."""
    if len(canonical_bytes(pkg.manifest)) > MAX_PACKAGE_BYTES:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "The package is too large.")
    signer = db_session.get(EvolvXSIPackSigner, pkg.key_id)
    if signer is None:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "The signer is not trusted. Register its key first.")
    if signer.revoked:
        _audit(user, AuditAction.PACK_INSTALL, f"Refused a pack signed by revoked signer {pkg.key_id}", pkg.key_id, AuditOutcome.DENIED)
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "The signer's key was revoked, so its packs cannot be installed.")
    try:
        verify(signer.public_key, pkg.signature, canonical_bytes(pkg.manifest))
    except SignatureProblem as e:
        _audit(user, AuditAction.PACK_INSTALL, f"Refused a pack: {e}", pkg.key_id, AuditOutcome.DENIED)
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, str(e)) from e
    try:
        manifest = Manifest.model_validate(pkg.manifest)
    except ValidationError as e:
        first = e.errors()[0]
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, f"The manifest is not valid: {'.'.join(str(x) for x in first['loc'])}: {first['msg']}") from e
    if db_session.scalar(select(EvolvXSIPackVersion.row_id).where(
            EvolvXSIPackVersion.pack_id == manifest.id, EvolvXSIPackVersion.version == manifest.version)):
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "That version is already installed. A change needs a new version number.")
    row = EvolvXSIPackVersion(pack_id=manifest.id, version=manifest.version, manifest=manifest.model_dump(mode="json"),
                              digest=digest(pkg.manifest), signature=pkg.signature, signer_key_id=pkg.key_id, active=False)
    db_session.add(row)
    db_session.commit()
    _audit(user, AuditAction.PACK_INSTALL, f"Installed {manifest.id} {manifest.version} (digest {row.digest[:12]}, signer {pkg.key_id})", manifest.id)
    return _vview(db_session, row)


@router.post("/admin/packs/{pack_id}/{version}/activate")
def activate(
    pack_id: str, version: str,
    user: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> VersionView:
    """Make this the one active version of the pack (an upgrade, or a rollback
    when it is older). Past tasks keep the version they started from."""
    v = db_session.scalar(select(EvolvXSIPackVersion).where(EvolvXSIPackVersion.pack_id == pack_id, EvolvXSIPackVersion.version == version))
    if v is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Pack version not found.")
    if _revoked(db_session, v.signer_key_id):
        _audit(user, AuditAction.PACK_ACTIVATE, f"Refused to activate {pack_id} {version}: signer revoked", pack_id, AuditOutcome.DENIED)
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This pack's signer was revoked, so it cannot be activated.")
    previous = db_session.scalar(select(EvolvXSIPackVersion.version).where(EvolvXSIPackVersion.pack_id == pack_id, EvolvXSIPackVersion.active.is_(True)))
    db_session.execute(update(EvolvXSIPackVersion).where(EvolvXSIPackVersion.pack_id == pack_id).values(active=False))
    v.active = True
    db_session.commit()
    kind = "Rolled back to" if previous and version_key(version) < version_key(previous) else "Activated"
    _audit(user, AuditAction.PACK_ACTIVATE, f"{kind} {pack_id} {version}" + (f" (was {previous})" if previous else ""), pack_id)
    return _vview(db_session, v)


@router.post("/admin/packs/{pack_id}/{version}/evaluate")
def evaluate_version(
    pack_id: str, version: str,
    user: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> VersionView:
    """Run the version's evaluation cases on the model in use now and record the
    result for that exact model. Cases carry their own evidence, so the result
    does not depend on what is indexed."""
    from evolvxsi.route_policy.enforce import check_route

    v = db_session.scalar(select(EvolvXSIPackVersion).where(EvolvXSIPackVersion.pack_id == pack_id, EvolvXSIPackVersion.version == version))
    if v is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Pack version not found.")
    manifest = Manifest.model_validate(v.manifest)
    if not manifest.evaluation_cases:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "This pack version has no evaluation cases.")
    model = current_model(db_session)
    if model is None:
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "There is no default model to evaluate on.")
    kind = check_route(db_session, model.id).kind
    results = evaluate(db_session, user, manifest)
    details = [{"question": r.question, "passed": r.passed, "reason": r.reason} for r in results]
    passed = all(r.passed for r in results)
    row = db_session.scalar(select(EvolvXSIPackEvaluation).where(
        EvolvXSIPackEvaluation.pack_id == pack_id, EvolvXSIPackEvaluation.version == version,
        EvolvXSIPackEvaluation.model_configuration_id == model.id))
    if row is None:
        row = EvolvXSIPackEvaluation(pack_id=pack_id, version=version, model_configuration_id=model.id, model_name=model.name,
                                     route_kind=kind, passed=passed, cases_total=len(results),
                                     cases_passed=sum(r.passed for r in results), details=details)
        db_session.add(row)
    else:
        row.passed, row.route_kind, row.cases_total = passed, kind, len(results)
        row.cases_passed, row.details, row.run_at = sum(r.passed for r in results), details, datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()
    _audit(user, AuditAction.PACK_EVALUATE,
           f"Evaluated {pack_id} {version} on {model.name} ({kind}): {'passed' if passed else 'failed'}, "
           f"{row.cases_passed} of {row.cases_total} cases", pack_id, AuditOutcome.SUCCESS if passed else AuditOutcome.FAILURE)
    return _vview(db_session, v)


@router.post("/admin/packs/{pack_id}/deactivate")
def deactivate(
    pack_id: str,
    user: User = Depends(require_permission(Permission.MANAGE_CONNECTORS)),
    db_session: Session = Depends(get_session),
) -> list[VersionView]:
    db_session.execute(update(EvolvXSIPackVersion).where(EvolvXSIPackVersion.pack_id == pack_id).values(active=False))
    db_session.commit()
    _audit(user, AuditAction.PACK_ACTIVATE, f"Deactivated {pack_id}", pack_id)
    return [_vview(db_session, v) for v in db_session.scalars(select(EvolvXSIPackVersion).where(EvolvXSIPackVersion.pack_id == pack_id))]


# ---- people ------------------------------------------------------------------

def _active_versions(db: Session) -> list[EvolvXSIPackVersion]:
    rows = db.scalars(select(EvolvXSIPackVersion).where(EvolvXSIPackVersion.active.is_(True)).order_by(EvolvXSIPackVersion.pack_id))
    # A revoked signer's pack is flagged for the administrator and not offered to people.
    return [v for v in rows if not _revoked(db, v.signer_key_id)]


@router.get("/packs")
def list_packs(
    _: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[PackView]:
    out = []
    for v in _active_versions(db_session):
        m = v.manifest
        ready, note = passed_on_current_model(db_session, v.pack_id, v.version, m)
        out.append(PackView(
            pack_id=v.pack_id, version=v.version, name=m["name"], vertical=m["vertical"], description=m.get("description", ""),
            templates=[TemplateView(**{k: t.get(k, "") for k in ("id", "title", "request", "desired_output")}) for t in m["templates"]],
            data_classes=m["requires"]["data_classes"], route_kinds=m["requires"]["route_kinds"],
            requests_send_destinations=bool(m.get("requests", {}).get("send_destinations")),
            ready_on_current_route=ready, readiness_note=None if ready else f"Not available on the current model: {note}.",
        ))
    return out


@router.post("/packs/{pack_id}/templates/{template_id}/task")
def start_from_template(
    pack_id: str, template_id: str,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """Create a draft task from a template of the active pack. Nothing runs; the
    owner can edit the draft and must press Start. The task remembers the exact
    pack version."""
    v = next((x for x in _active_versions(db_session) if x.pack_id == pack_id), None)
    if v is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Pack not found.")
    t = next((x for x in v.manifest["templates"] if x["id"] == template_id), None)
    if t is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Template not found.")
    rules = list(v.manifest.get("review_rules", [])) + list(t.get("review_rules", []))
    task = EvolvXSITask(
        owner_id=user.id, title=t["title"], request=t["request"], desired_output=t.get("desired_output", ""),
        state=TaskState.DRAFT.value, version=1, pack_id=v.pack_id, pack_version=v.version, pack_template=template_id,
        review_rules=rules or None,
    )
    db_session.add(task)
    db_session.commit()
    return _view(task)
