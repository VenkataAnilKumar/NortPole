from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission
from nortpole.db.models import LLMProvider, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.utils.audit import AuditAction, AuditOutcome
from nortpole.governance.route_policy.audit import describe_policy_change, list_audit, record_audit
from nortpole.governance.route_policy.policy import (
    AUTO_PREFERENCE,
    DATA_CLASSES,
    ROUTE_KINDS,
    RouteDecision,
    RoutePolicy,
    decide,
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
    redact_route_kinds: list[str]
    routes: list[RouteView]
    auto_provider_id: int | None


class RoutePolicyUpdate(BaseModel):
    default_data_class: str | None = None
    allowed: dict[str, list[str]] | None = None
    route_kinds: dict[str, str] | None = None
    redact_route_kinds: list[str] | None = None


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
        redact_route_kinds=policy.redact_route_kinds,
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


def plan_policy_update(update: RoutePolicyUpdate, db_session: Session) -> tuple[RoutePolicy, RoutePolicy]:
    """The policy as it is now and as it would be after this update. Raises if the update is not valid."""
    current = load_policy()
    try:
        new = RoutePolicy(
            version=current.version + 1,
            default_data_class=update.default_data_class or current.default_data_class,
            allowed=update.allowed if update.allowed is not None else current.allowed,
            route_kinds=update.route_kinds if update.route_kinds is not None else current.route_kinds,
            redact_route_kinds=update.redact_route_kinds if update.redact_route_kinds is not None else current.redact_route_kinds,
        )
    except ValueError as exc:
        raise NortPoleError(NortPoleErrorCode.VALIDATION_ERROR, str(exc)) from exc
    ids = {str(p.id) for p in db_session.query(LLMProvider.id).all()}
    unknown = set(new.route_kinds) - ids
    if unknown:
        raise NortPoleError(
            NortPoleErrorCode.VALIDATION_ERROR,
            f"Unknown provider id(s): {', '.join(sorted(unknown))}",
        )
    return current, new


def apply_policy_update(
    update: RoutePolicyUpdate, db_session: Session, actor: User | None, *,
    approver_email: str | None = None, expect_version: int | None = None,
) -> RoutePolicy:
    """Save the update and audit it. `expect_version` refuses it if the policy changed since it was proposed."""
    current, new = plan_policy_update(update, db_session)
    if expect_version is not None and current.version != expect_version:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The route policy changed after this was proposed. Propose it again.")
    save_policy(new)
    summary, details = describe_policy_change(current, new)
    if approver_email:
        details = {**(details or {}), "proposed_by": getattr(actor, "email", None), "approved_by": approver_email}
    record_audit(
        AuditAction.ROUTE_POLICY_CHANGE,
        AuditOutcome.SUCCESS,
        actor=actor,
        summary=summary,
        details=details,
        resource_type="route_policy",
        resource_id=new.version,
    )
    return new


@router.put("/admin/route-policy")
def put_route_policy(
    update: RoutePolicyUpdate,
    user: User = Depends(require_permission(Permission.MANAGE_LLMS)),
    db_session: Session = Depends(get_session),
) -> RoutePolicyView:
    from nortpole.governance.admin_changes import controls
    from nortpole.governance.admin_changes.service import propose, pending_response

    if controls.required("route_policy"):
        # Checked now so the proposer learns of a mistake at once; applied only when a second administrator approves.
        current, new = plan_policy_update(update, db_session)
        summary, _ = describe_policy_change(current, new)
        return pending_response(propose(db_session, user, "route_policy", update.model_dump(), current.version, summary))  # type: ignore[return-value]
    new = apply_policy_update(update, db_session, user)
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


class UsageRow(BaseModel):
    route_kind: str
    model_name: str
    data_class: str
    purpose: str
    requests: int


@router.get("/admin/route-usage")
def get_route_usage(
    days: int = 30,
    _: User = Depends(require_permission(Permission.MANAGE_LLMS)),
    db_session: Session = Depends(get_session),
) -> list[UsageRow]:
    """Allowed model requests over the last `days` days (1 to 365), by route, model,
    data class and purpose. Request counts only; no people, text, tokens or cost."""
    from nortpole.governance.route_policy.usage import total

    return [UsageRow(route_kind=r[0], model_name=r[1], data_class=r[2], purpose=r[3], requests=int(r[4]))
            for r in total(db_session, min(max(days, 1), 365))]


class TokenRow(BaseModel):
    route_kind: str
    model_name: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_cents: float | None  # None when no call on this row had a known price
    unpriced_calls: int


@router.get("/admin/route-tokens")
def get_route_tokens(
    days: int = 30,
    _: User = Depends(require_permission(Permission.MANAGE_LLMS)),
    db_session: Session = Depends(get_session),
) -> list[TokenRow]:
    """Tokens the models reported using over the last `days` days (1 to 365), by route type and model, with an
    estimated cost in cents from the price list. The cost counts only calls whose price is known; `unpriced_calls`
    says how many were left out. Counters only: no people and no text."""
    from nortpole.governance.route_policy.usage import total_tokens

    out = []
    for kind, model, calls, prompt, completion, cost, unpriced in total_tokens(db_session, min(max(days, 1), 365)):
        calls, unpriced = int(calls), int(unpriced)
        out.append(TokenRow(route_kind=kind, model_name=model, calls=calls, prompt_tokens=int(prompt), completion_tokens=int(completion),
                            estimated_cost_cents=round(float(cost), 4) if calls > unpriced else None, unpriced_calls=unpriced))
    return out
