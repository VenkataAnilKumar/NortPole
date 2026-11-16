"""The integration catalog for people, and the administrator's policy (decision 0008, phase 2b-2).

People (any signed-in user): browse the catalog with their own state for each item, install, connect their own account
and remove. Administrators: see the policy for every item with how many people use it, and change it. No route here
returns a credential; a person's account goes in and is only ever used to make a call."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.utils.audit import AuditAction, AuditOutcome
from nortpole.work.integrations import policy, registry, service
from nortpole.work.integrations.manifest import Integration
from nortpole.work.integrations.models import NortPoleIntegrationUse
from nortpole.work.integrations.service import IntegrationAccessError

router = APIRouter()

ERROR_CODES = {
    "unknown_integration": NortPoleErrorCode.NOT_FOUND,
    "unknown_action": NortPoleErrorCode.NOT_FOUND,
    "blocked": NortPoleErrorCode.POLICY_BLOCKED,
    "needs_approval": NortPoleErrorCode.POLICY_BLOCKED,
    "not_installed": NortPoleErrorCode.CONFLICT,
    "not_connected": NortPoleErrorCode.CONFLICT,
    "bad_settings": NortPoleErrorCode.INVALID_INPUT,
    "bad_credential": NortPoleErrorCode.INVALID_INPUT,
    "no_account_needed": NortPoleErrorCode.INVALID_INPUT,
    "secrets_key_missing": NortPoleErrorCode.FEATURE_DISABLED,
}


def _refuse(exc: IntegrationAccessError) -> NortPoleError:
    return NortPoleError(ERROR_CODES.get(exc.code, NortPoleErrorCode.BAD_REQUEST), str(exc))


class IntegrationActionView(BaseModel):
    id: str
    name: str
    description: str
    effect: str


class IntegrationView(BaseModel):
    id: str
    name: str
    description: str
    kind: str
    group: str
    category: str
    version: str
    hosts: list[str]
    data_classes: list[str]
    needs_account: bool
    has_writes: bool
    actions: list[IntegrationActionView]
    # The person's own state: available, needs_approval, blocked, installed or connected.
    state: str
    policy: str
    installed_version: str | None
    update_available: bool


class IntegrationCatalog(BaseModel):
    items: list[IntegrationView]


class IntegrationInstallBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # The parameters only the person may set (for example how many results), by name.
    settings: dict[str, Any] = Field(default_factory=dict)


class IntegrationAccountBody(BaseModel):
    """The person's own account. Which field depends on how the integration signs in: `access_token` for an OAuth
    integration (a personal access token until the sign-in flow ships), `api_key` for an API-key integration."""

    model_config = ConfigDict(extra="forbid")
    access_token: str | None = Field(default=None, max_length=4000, repr=False)
    api_key: str | None = Field(default=None, max_length=4000, repr=False)


def _view(item: Integration, state: dict[str, Any]) -> IntegrationView:
    return IntegrationView(
        id=item.id, name=item.name, description=item.description, kind=item.kind, group=item.group, category=item.category,
        version=item.version, hosts=item.hosts, data_classes=list(item.data_classes), needs_account=item.auth.mode != "none",
        has_writes=any(a.effect == "write" for a in item.actions),
        actions=[IntegrationActionView(id=a.id, name=a.name, description=a.description, effect=a.effect) for a in item.actions],
        state=state["state"], policy=state["policy"], installed_version=state["installed_version"],
        update_available=state["installed_version"] is not None and state["installed_version"] != item.version,
    )


@router.get("/integrations")
def catalog(
    group: str | None = Query(default=None, pattern="^(horizontal|vertical)$"),
    category: str | None = Query(default=None, max_length=40),
    kind: str | None = Query(default=None, pattern="^(connector|plugin)$"),
    q: str | None = Query(default=None, max_length=100),
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> IntegrationCatalog:
    """Everything this deployment offers, grouped Horizontal then Vertical, with the person's own state for each."""
    config = policy.load()
    items = []
    for item in registry.all_integrations().values():
        if (group and item.group != group) or (category and item.category != category) or (kind and item.kind != kind):
            continue
        if q and q.lower() not in f"{item.name} {item.description} {item.category}".lower():
            continue
        items.append(_view(item, service.status(db, user, item.id, config)))
    items.sort(key=lambda v: (v.group, v.category, v.name.lower()))
    return IntegrationCatalog(items=items)


@router.get("/integrations/{integration_id}")
def detail(
    integration_id: str,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> IntegrationView:
    item = registry.get(integration_id)
    if item is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "That integration is not offered here.")
    return _view(item, service.status(db, user, integration_id))


@router.post("/integrations/{integration_id}/install")
def install(
    integration_id: str,
    body: IntegrationInstallBody,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> IntegrationView:
    try:
        service.install(db, user, integration_id, body.settings)
    except IntegrationAccessError as exc:
        raise _refuse(exc) from exc
    return _view(registry.get(integration_id), service.status(db, user, integration_id))  # type: ignore[arg-type]


@router.delete("/integrations/{integration_id}")
def remove(
    integration_id: str,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> IntegrationView:
    try:
        service.remove(db, user, integration_id)
    except IntegrationAccessError as exc:
        raise _refuse(exc) from exc
    return _view(registry.get(integration_id), service.status(db, user, integration_id))  # type: ignore[arg-type]


@router.put("/integrations/{integration_id}/account")
def connect(
    integration_id: str,
    body: IntegrationAccountBody,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> IntegrationView:
    credential = {k: v for k, v in (("access_token", body.access_token), ("api_key", body.api_key)) if v}
    try:
        service.connect(db, user, integration_id, credential)
    except IntegrationAccessError as exc:
        raise _refuse(exc) from exc
    return _view(registry.get(integration_id), service.status(db, user, integration_id))  # type: ignore[arg-type]


@router.delete("/integrations/{integration_id}/account")
def disconnect(
    integration_id: str,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> IntegrationView:
    try:
        service.disconnect(db, user, integration_id)
    except IntegrationAccessError as exc:
        raise _refuse(exc) from exc
    return _view(registry.get(integration_id), service.status(db, user, integration_id))  # type: ignore[arg-type]


# ---- the administrator's policy -------------------------------------------------------------------------------------


class IntegrationPolicyRow(BaseModel):
    id: str
    name: str
    kind: str
    group: str
    category: str
    has_writes: bool
    default: str
    override: str | None
    category_override: str | None
    effective: str
    installs: int
    connected: int


class IntegrationPolicyView(BaseModel):
    config: policy.PolicyConfig
    items: list[IntegrationPolicyRow]


class IntegrationPolicyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: policy.PolicyConfig
    # Needed when the change lets people use a write action without asking first.
    acknowledge_writes: bool = False


def _policy_view(db: Session) -> IntegrationPolicyView:
    config = policy.load()
    counts = {
        row[0]: (row[1], row[2])
        for row in db.execute(
            select(NortPoleIntegrationUse.integration_id, func.count(), func.count(NortPoleIntegrationUse.credential))
            .group_by(NortPoleIntegrationUse.integration_id)
        ).all()
    }
    rows = []
    for item in registry.all_integrations().values():
        installs, connected = counts.get(item.id, (0, 0))
        rows.append(IntegrationPolicyRow(
            id=item.id, name=item.name, kind=item.kind, group=item.group, category=item.category,
            has_writes=any(a.effect == "write" for a in item.actions), default=item.policy_default,
            override=config.integrations.get(item.id), category_override=config.categories.get(f"{item.group}/{item.category}"),
            effective=policy.resolve(item, config), installs=installs, connected=connected,
        ))
    rows.sort(key=lambda r: (r.group, r.category, r.name.lower()))
    return IntegrationPolicyView(config=config, items=rows)


@router.get("/admin/integrations/policy")
def get_policy(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db: Session = Depends(get_session),
) -> IntegrationPolicyView:
    return _policy_view(db)


@router.put("/admin/integrations/policy")
def put_policy(
    body: IntegrationPolicyBody,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db: Session = Depends(get_session),
) -> IntegrationPolicyView:
    offered = registry.all_integrations()
    unknown = sorted(set(body.config.integrations) - set(offered))
    if unknown:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, f"These are not offered here: {', '.join(unknown)}.")
    before = policy.load()
    # Which write-capable integrations would now be open to everyone without asking?
    def opened(config: policy.PolicyConfig) -> set[str]:
        return {i.id for i in offered.values() if any(a.effect == "write" for a in i.actions) and policy.resolve(i, config) == "allowed"}

    newly_open = sorted(opened(body.config) - opened(before))
    if newly_open and not body.acknowledge_writes:
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT,
            f"This lets people use write actions without asking first: {', '.join(newly_open)}. Confirm to continue.",
        )
    policy.save(body.config)
    changed = {
        "integrations": {k: [before.integrations.get(k), body.config.integrations.get(k)]
                         for k in set(before.integrations) | set(body.config.integrations)
                         if before.integrations.get(k) != body.config.integrations.get(k)},
        "categories": {k: [before.categories.get(k), body.config.categories.get(k)]
                       for k in set(before.categories) | set(body.config.categories)
                       if before.categories.get(k) != body.config.categories.get(k)},
    }
    from nortpole.governance.route_policy.audit import record_audit

    record_audit(
        AuditAction.INTEGRATION_POLICY_CHANGE, AuditOutcome.SUCCESS, actor=user,
        summary=f"Changed the integration policy ({len(changed['integrations'])} integration(s), {len(changed['categories'])} categor(ies))",
        details={**changed, "opens_writes": newly_open}, resource_type="integration_policy", resource_id="policy",
    )
    return _policy_view(db)
