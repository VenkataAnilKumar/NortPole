from __future__ import annotations

from sqlalchemy.orm import Session

from evolvxsi.db.models import ModelConfiguration
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.route_policy.policy import RouteDecision, decide, load_policy
from evolvxsi.utils.logger import setup_logger

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
) -> RouteDecision:
    """Raise POLICY_BLOCKED before any content is sent to a blocked route."""
    decision = check_route(db_session, model_configuration_id, data_class)
    logger.info(
        "route_policy decision allowed=%s kind=%s data_class=%s model_configuration_id=%s",
        decision.allowed,
        decision.kind,
        decision.data_class,
        model_configuration_id,
    )
    if not decision.allowed:
        raise EvolvXSIError(
            EvolvXSIErrorCode.POLICY_BLOCKED,
            decision.reason or "This model route is not allowed for this data class.",
        )
    return decision
