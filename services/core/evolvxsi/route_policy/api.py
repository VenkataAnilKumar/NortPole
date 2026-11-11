from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import LLMProvider, User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.utils.audit import AuditAction, AuditOutcome
from evolvxsi.route_policy.audit import describe_policy_change, list_audit, record_audit
from evolvxsi.route_policy.policy import (
    AUTO_PREFERENCE,
    DATA_CLASSES,
    ROUTE_KINDS,
    RouteDecision,
    RoutePolicy,
    decide,
    kind_for,
    load_policy,
    save_policy,
)

router = APIRouter()


class RouteView(BaseModel):
    provider_id: int
    name: str | None
    provider: str
    model_names: list[str]
    kind: str
    kind_assigned: bool
    allowed: bool
    reason: str | None


class RoutePolicyView(BaseModel):
    version: int
    data_class: str
    default_data_class: str
    data_classes: list[str]
    route_kinds: list[str]
    allowed: dict[str, list[str]]
    routes: list[RouteView]
    auto_provider_id: int | None


class RoutePolicyUpdate(BaseModel):
    default_data_class: str | None = None
    allowed: dict[str, list[str]] | None = None
    route_kinds: dict[str, str] | None = None


class RouteCheckRequest(BaseModel):
    provider_id: int
    data_class: str | None = None


def _view(policy: RoutePolicy, db_session: Session, data_class: str | None) -> RoutePolicyView:
    cls = data_class if data_class in DATA_CLASSES else policy.default_data_class
    providers = db_session.query(LLMProvider).order_by(LLMProvider.id).all()
    routes: list[RouteView] = []
    for p in providers:
        d = decide(policy, p.id, cls)
        routes.append(
            RouteView(
                provider_id=p.id,
                name=p.name,
                provider=p.provider,
                model_names=[m.name for m in p.model_configurations if m.is_visible],
                kind=d.kind,
                kind_assigned=str(p.id) in policy.route_kinds,
                allowed=d.allowed,
                reason=d.reason,
            )
        )
    auto: int | None = None
    for kind in AUTO_PREFERENCE:
        match = next((r for r in routes if r.allowed and r.kind == kind and r.model_names), None)
        if match:
            auto = match.provider_id
            break
    return RoutePolicyView(
        version=policy.version,
        data_class=cls,
        default_data_class=policy.default_data_class,
        data_classes=list(DATA_CLASSES),
        route_kinds=list(ROUTE_KINDS),
        allowed=policy.allowed,
        routes=routes,
        auto_provider_id=auto,
    )


@router.get("/route-policy")
def get_route_policy(
    data_class: str | None = None,
    _: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> RoutePolicyView:
    return _view(load_policy(), db_session, data_class)


@router.post("/route-policy/check")
def check_route_policy(
    request: RouteCheckRequest,
    _: User = Depends(require_permission(Permission.BASIC_ACCESS)),
) -> RouteDecision:
    return decide(load_policy(), request.provider_id, request.data_class)


@router.put("/admin/route-policy")
def put_route_policy(
    update: RoutePolicyUpdate,
    user: User = Depends(require_permission(Permission.MANAGE_LLMS)),
    db_session: Session = Depends(get_session),
) -> RoutePolicyView:
    current = load_policy()
    try:
        new = RoutePolicy(
            version=current.version + 1,
            default_data_class=update.default_data_class or current.default_data_class,
            allowed=update.allowed if update.allowed is not None else current.allowed,
            route_kinds=update.route_kinds if update.route_kinds is not None else current.route_kinds,
        )
    except ValueError as exc:
        raise EvolvXSIError(EvolvXSIErrorCode.VALIDATION_ERROR, str(exc)) from exc
    ids = {str(p.id) for p in db_session.query(LLMProvider.id).all()}
    unknown = set(new.route_kinds) - ids
    if unknown:
        raise EvolvXSIError(
            EvolvXSIErrorCode.VALIDATION_ERROR,
            f"Unknown provider id(s): {', '.join(sorted(unknown))}",
        )
    save_policy(new)
    summary, details = describe_policy_change(current, new)
    record_audit(
        AuditAction.ROUTE_POLICY_CHANGE,
        AuditOutcome.SUCCESS,
        actor=user,
        summary=summary,
        details=details,
        resource_type="route_policy",
        resource_id=new.version,
    )
    return _view(new, db_session, None)


class AuditEventView(BaseModel):
    id: int
    created_at: str
    action: str
    outcome: str
    actor_email: str | None
    summary: str
    details: dict | None


@router.get("/admin/route-policy/audit")
def get_route_audit(
    limit: int = 50,
    action: str | None = None,
    _: User = Depends(require_permission(Permission.MANAGE_LLMS)),
    db_session: Session = Depends(get_session),
) -> list[AuditEventView]:
    return [
        AuditEventView(
            id=e.id,
            created_at=e.created_at.isoformat(),
            action=e.action,
            outcome=e.outcome,
            actor_email=e.actor_email,
            summary=e.summary,
            details=e.details,
        )
        for e in list_audit(db_session, limit, action)
    ]
