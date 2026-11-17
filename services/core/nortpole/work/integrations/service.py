"""A person's use of integrations: install, connect, disconnect, remove, and make a call (decision 0008, phase 2b).

The order of checks for a call is fixed and the same for a chat and a workflow: the integration exists, the policy has not
blocked it, the person installed it, and (when it needs an account) the person connected theirs. Only then does the
executor run, with the person's own credential. Accounts are sealed before they are stored. Installing needs the policy to allow it, or an approved request from that
person; connecting needs the integration to be installed first. Nothing here reads or returns a credential except the
call itself."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from nortpole.db.models import User
from nortpole.knowledge.source_requests import catalog
from nortpole.knowledge.source_requests.models import NortPoleSourceRequest
from nortpole.utils.audit import AuditAction, AuditOutcome
from nortpole.work.integrations import executor, oauth, policy, registry, secrets
from nortpole.work.integrations.manifest import Integration
from nortpole.work.integrations.models import NortPoleIntegrationUse

CREDENTIAL_FIELDS = {"oauth": ("access_token", "refresh_token", "expires_at"), "api_key": ("api_key",)}


class IntegrationAccessError(Exception):
    """A refusal a person can be shown: it names what to do, never a secret."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _definition(integration_id: str) -> Integration:
    found = registry.get(integration_id)
    if found is None:
        raise IntegrationAccessError("unknown_integration", "That integration is not offered here.")
    return found


def _audit(user: User, action: AuditAction, outcome: AuditOutcome, integration: Integration, summary: str, **details: Any) -> None:
    from nortpole.governance.route_policy.audit import record_audit

    record_audit(
        action, outcome, actor=user, summary=summary,
        details={"integration": integration.id, "version": integration.version, **details},
        resource_type="integration", resource_id=integration.id,
    )


def _use(db: Session, user: User, integration_id: str) -> NortPoleIntegrationUse | None:
    return db.scalar(select(NortPoleIntegrationUse).where(NortPoleIntegrationUse.user_id == user.id, NortPoleIntegrationUse.integration_id == integration_id))


def _approved_for(db: Session, user: User, integration: Integration) -> bool:
    return db.scalar(
        select(NortPoleSourceRequest.id).where(
            NortPoleSourceRequest.requested_by_id == user.id,
            NortPoleSourceRequest.kind == integration.kind,
            NortPoleSourceRequest.item_key == catalog.integration_key(integration.id),
            NortPoleSourceRequest.state == "approved",
        ).limit(1)
    ) is not None


def status(db: Session, user: User, integration_id: str, config: policy.PolicyConfig | None = None) -> dict[str, Any]:
    """What the catalog shows for one integration and one person. Never a credential."""
    integration = _definition(integration_id)
    answer = policy.resolve(integration, config)
    use = _use(db, user, integration_id)
    approved = answer == "needs_approval" and _approved_for(db, user, integration)
    if use is not None:
        state = "connected" if use.credential is not None else "installed"
    elif answer == "blocked":
        state = "blocked"
    elif answer == "allowed" or approved:
        state = "available"
    else:
        state = "needs_approval"
    return {"id": integration.id, "state": state, "policy": answer, "needs_account": integration.auth.mode != "none",
            "installed_version": use.version if use else None, "latest_version": integration.version}


def install(db: Session, user: User, integration_id: str, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    integration = _definition(integration_id)
    answer = policy.resolve(integration)
    if answer == "blocked":
        _audit(user, AuditAction.INTEGRATION_INSTALL, AuditOutcome.DENIED, integration, f"Refused: {integration.name} is blocked", reason="blocked")
        raise IntegrationAccessError("blocked", f"{integration.name} is blocked by your administrator.")
    if answer == "needs_approval" and not _approved_for(db, user, integration):
        _audit(user, AuditAction.INTEGRATION_INSTALL, AuditOutcome.DENIED, integration, f"Refused: {integration.name} needs approval", reason="needs_approval")
        raise IntegrationAccessError("needs_approval", f"{integration.name} needs your administrator's approval. Send a request first.")
    chosen = _check_settings(integration, settings or {})
    use = _use(db, user, integration_id)
    if use is None:
        db.add(NortPoleIntegrationUse(id=uuid.uuid4(), user_id=user.id, integration_id=integration.id, version=integration.version, settings=chosen))
    else:
        use.settings, use.version = chosen, integration.version
    db.commit()
    _audit(user, AuditAction.INTEGRATION_INSTALL, AuditOutcome.SUCCESS, integration, f"Installed {integration.name}")
    return status(db, user, integration_id)


def _check_settings(integration: Integration, settings: dict[str, Any]) -> dict[str, Any]:
    """Settings are the parameters only the person may set (`fill: user`); each is checked like a call's parameters."""
    allowed = {n for a in integration.actions for n, p in a.params.items() if p.fill == "user"}
    unknown = set(settings) - allowed
    if unknown:
        raise IntegrationAccessError("bad_settings", f"These are not settings of {integration.name}: {', '.join(sorted(unknown))}.")
    for action in integration.actions:
        for name, value in settings.items():
            param = action.params.get(name)
            if param is not None and param.fill == "user":
                try:
                    executor._check(name, param, value)
                except executor.IntegrationCallError as exc:
                    raise IntegrationAccessError("bad_settings", str(exc)) from exc
    return dict(settings)


def remove(db: Session, user: User, integration_id: str) -> None:
    integration = _definition(integration_id)
    use = _use(db, user, integration_id)
    if use is None:
        return
    had_account = use.credential is not None
    db.delete(use)
    db.commit()
    _audit(user, AuditAction.INTEGRATION_REMOVE, AuditOutcome.SUCCESS, integration, f"Removed {integration.name}", disconnected=had_account)


def connect(db: Session, user: User, integration_id: str, credential: dict[str, Any]) -> dict[str, Any]:
    """Store the person's own account for an integration they installed. The credential is encrypted at rest."""
    integration = _definition(integration_id)
    if integration.auth.mode == "none":
        raise IntegrationAccessError("no_account_needed", f"{integration.name} needs no account.")
    use = _use(db, user, integration_id)
    if use is None:
        raise IntegrationAccessError("not_installed", f"Install {integration.name} first.")
    if policy.resolve(integration) == "blocked":
        raise IntegrationAccessError("blocked", f"{integration.name} is blocked by your administrator.")
    fields = CREDENTIAL_FIELDS[integration.auth.mode]
    clean = {k: v for k, v in credential.items() if k in fields and isinstance(v, (str, int)) and str(v)}
    required = fields[0]
    if required not in clean or any(k not in fields for k in credential):
        raise IntegrationAccessError("bad_credential", f"That is not a usable {integration.auth.mode.replace('_', ' ')} for {integration.name}.")
    try:
        use.credential = secrets.seal(clean)
    except secrets.SecretsError as exc:
        raise IntegrationAccessError(exc.code, str(exc)) from exc
    use.connected_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    _audit(user, AuditAction.INTEGRATION_CONNECT, AuditOutcome.SUCCESS, integration, f"Connected {integration.name}", mode=integration.auth.mode)
    return status(db, user, integration_id)


def disconnect(db: Session, user: User, integration_id: str) -> dict[str, Any]:
    integration = _definition(integration_id)
    use = _use(db, user, integration_id)
    if use is not None and use.credential is not None:
        use.credential, use.connected_at = None, None
        db.commit()
        _audit(user, AuditAction.INTEGRATION_DISCONNECT, AuditOutcome.SUCCESS, integration, f"Disconnected {integration.name}")
    return status(db, user, integration_id)


def ready(db: Session, user: User, integration_id: str, action_id: str) -> tuple[Integration, NortPoleIntegrationUse, Any]:
    """The checks before any call, in a fixed order: it exists, policy has not blocked it, the person installed it, connected
    it (when it needs an account), and has this action."""
    integration = _definition(integration_id)
    if policy.resolve(integration) == "blocked":
        raise IntegrationAccessError("blocked", f"{integration.name} is blocked by your administrator.")
    use = _use(db, user, integration_id)
    if use is None:
        raise IntegrationAccessError("not_installed", f"{integration.name} is not installed for you.")
    if integration.auth.mode != "none" and use.credential is None:
        raise IntegrationAccessError("not_connected", f"Connect your {integration.name} account first.")
    action = next((a for a in integration.actions if a.id == action_id), None)
    if action is None:
        raise IntegrationAccessError("unknown_action", f"{integration.name} has no action {action_id}.")
    return integration, use, action


def check_arguments(db: Session, user: User, integration_id: str, action_id: str, arguments: dict[str, Any]) -> tuple[Integration, Any]:
    """Everything `call` checks, and the arguments too, but nothing is sent: a proposal that could never run is refused
    when it is made, so the person is never asked to approve it."""
    integration, use, action = ready(db, user, integration_id, action_id)
    try:
        account = secrets.unseal(use.credential) if use.credential is not None else None
    except secrets.SecretsError as exc:
        raise IntegrationAccessError("not_connected" if exc.code == "secrets_unreadable" else exc.code, str(exc)) from exc
    settings = {k: v for k, v in (use.settings or {}).items() if k in action.params}
    executor.prepare(integration, action_id, user_params=settings, model_params=arguments, credential=account)
    return integration, action


def call(
    db: Session,
    user: User,
    integration_id: str,
    action_id: str,
    *,
    model_params: dict[str, Any] | None = None,
    transport: executor.Transport | None = None,
) -> dict[str, Any]:
    """Make one call as this person. Checks run in a fixed order and each refusal says what to do."""
    integration, use, action = ready(db, user, integration_id, action_id)
    try:
        account = secrets.unseal(use.credential) if use.credential is not None else None
    except secrets.SecretsError as exc:
        raise IntegrationAccessError("not_connected" if exc.code == "secrets_unreadable" else exc.code, str(exc)) from exc
    if account is not None and integration.auth.mode == "oauth" and oauth.needs_refresh(account):
        try:
            account = oauth.refresh(integration.auth.provider or "", account)
            use.credential = secrets.seal(account)
            db.commit()
        except (oauth.OAuthError, secrets.SecretsError):
            raise IntegrationAccessError("not_connected", f"Your {integration.name} sign-in ran out and could not be renewed. Connect it again.") from None
    # The person's settings fill only parameters meant for the person, and only those this action has; the model's
    # values fill only those meant for it. The executor enforces both again.
    settings = {k: v for k, v in (use.settings or {}).items() if k in action.params}
    return executor.run(
        integration, action_id, user_params=settings, model_params=model_params,
        credential=account, user_id=str(user.id), transport=transport,
    )
