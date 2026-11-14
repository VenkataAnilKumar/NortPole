from __future__ import annotations

from sqlalchemy.orm import Session

from nortpole.db.models import ModelConfiguration, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.audit import record_audit
from nortpole.governance.route_policy.policy import RouteDecision, decide, load_policy
from nortpole.utils.audit import AuditAction, AuditOutcome
from nortpole.utils.logger import setup_logger

logger = setup_logger()


def provider_id_for_model_configuration(
    db_session: Session, model_configuration_id: int | None
) -> int | None:
    if model_configuration_id is None:
        return None
    row = db_session.get(ModelConfiguration, model_configuration_id)
    return row.llm_provider_id if row else None


def check_route(
    db_session: Session,
    model_configuration_id: int | None,
    data_class: str | None = None,
) -> RouteDecision:
    policy = load_policy()
    provider_id = provider_id_for_model_configuration(db_session, model_configuration_id)
    # Fail closed: a model we cannot place on a provider is treated as an
    # unassigned (cloud) route, so it is blocked wherever cloud is blocked.
    return decide(policy, provider_id if provider_id is not None else -1, data_class)


def enforce_route(
    db_session: Session,
    model_configuration_id: int | None,
    data_class: str | None = None,
    actor: User | None = None,
    purpose: str | None = None,
) -> RouteDecision:
    """Raise POLICY_BLOCKED before any content is sent to a blocked route. When a
    purpose is given, an allowed request is counted (see usage.py)."""
    decision = check_route(db_session, model_configuration_id, data_class)
    logger.info(
        "route_policy decision allowed=%s kind=%s data_class=%s model_configuration_id=%s",
        decision.allowed,
        decision.kind,
        decision.data_class,
        model_configuration_id,
    )
    if not decision.allowed:
        record_audit(
            AuditAction.ROUTE_BLOCKED,
            AuditOutcome.DENIED,
            actor=actor,
            summary=decision.reason or "Request to a blocked route was refused before sending.",
            details={
                "model_configuration_id": model_configuration_id,
                "route_kind": decision.kind,
                "data_class": decision.data_class,
            },
            resource_type="model_route",
            resource_id=model_configuration_id,
        )
        raise NortPoleError(
            NortPoleErrorCode.POLICY_BLOCKED,
            decision.reason or "This model route is not allowed for this data class.",
        )
    if purpose:
        from nortpole.governance.route_policy.usage import record_usage

        row = db_session.get(ModelConfiguration, model_configuration_id) if model_configuration_id is not None else None
        record_usage(route_kind=decision.kind, provider_id=row.llm_provider_id if row else None,
                     model_name=row.name if row else "unknown", data_class=decision.data_class, purpose=purpose)
    return decision


def default_route_kind(db_session: Session) -> str | None:
    """The route kind (local, private or cloud) of the default chat model, or
    None when there is no default model."""
    from nortpole.db.enums import LLMModelFlowType
    from nortpole.db.llm import fetch_default_model

    model = fetch_default_model(db_session, LLMModelFlowType.CHAT)
    if model is None:
        return None
    return check_route(db_session, model.id).kind
