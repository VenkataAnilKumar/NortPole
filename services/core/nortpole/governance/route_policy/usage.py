"""Count the model requests that were allowed, by day, route, model, data class
and purpose. Counters only: no person, no prompt, no text. Blocked requests are
in the audit log with the person; this answers "what actually ran where".
The request counter is taken when the route is checked, before any token is
used. Tokens and an estimated cost are counted separately (NortPoleRouteTokens),
once the model has answered and reported its usage.""" 

from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, Date, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import Base
from nortpole.utils.logger import setup_logger

logger = setup_logger()

class NortPoleRouteUsage(Base):
    __tablename__ = "nortpole_route_usage"
    __table_args__ = (
        UniqueConstraint("day", "route_kind", "provider_id", "model_name", "data_class", "purpose", name="uq_nortpole_route_usage"),
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    route_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    data_class: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def record_usage(*, route_kind: str, provider_id: int | None, model_name: str, data_class: str, purpose: str) -> None:
    """Add one to the day's counter. Never raises: counting must not stop a request."""
    try:
        values = dict(day=datetime.date.today(), route_kind=route_kind, provider_id=provider_id if provider_id is not None else -1,
                      model_name=model_name, data_class=data_class, purpose=purpose, requests=1)
        with get_session_with_current_tenant() as s:
            stmt = insert(NortPoleRouteUsage).values(**values)
            stmt = stmt.on_conflict_do_update(constraint="uq_nortpole_route_usage",
                                              set_={"requests": NortPoleRouteUsage.requests + 1})
            s.execute(stmt)
            s.commit()
    except Exception:  # noqa: BLE001
        logger.warning("route usage was not recorded", exc_info=True)


def total(db, days: int):  # type: ignore[no-untyped-def]
    since = datetime.date.today() - datetime.timedelta(days=max(days, 1) - 1)
    q = (
        db.query(NortPoleRouteUsage.route_kind, NortPoleRouteUsage.model_name, NortPoleRouteUsage.data_class,
                 NortPoleRouteUsage.purpose, func.sum(NortPoleRouteUsage.requests))
        .filter(NortPoleRouteUsage.day >= since)
        .group_by(NortPoleRouteUsage.route_kind, NortPoleRouteUsage.model_name, NortPoleRouteUsage.data_class, NortPoleRouteUsage.purpose)
        .order_by(func.sum(NortPoleRouteUsage.requests).desc())
    )
    return q.all()


class NortPoleRouteTokens(Base):
    """Tokens the model reported using, and an estimated cost, by day, route type, provider and model.
    Counters only: no person, no prompt, no text. The cost is an estimate from the price list, in cents,
    counted only for calls whose price is known; `unpriced_calls` says how many were not."""

    __tablename__ = "nortpole_route_tokens"
    __table_args__ = (UniqueConstraint("day", "route_kind", "provider_id", "model_name", name="uq_nortpole_route_tokens"),)

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    route_kind: Mapped[str] = mapped_column(String(20), nullable=False)  # local, private, cloud or unknown
    provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost_cents: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    unpriced_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def is_priced(cost_cents: float, route_kind: str, locally_hosted: bool) -> bool:
    """Whether a call's cost is known. A positive cost from the price list is known. A call on a route the
    administrator marked local, or on a provider that runs on this deployment's own hardware, costs nothing per
    token, so zero is its real price. A zero on a private or cloud route means the price list had no entry,
    which is not the same as free."""
    return cost_cents > 0 or route_kind == "local" or locally_hosted


def record_tokens(*, model_configuration_id: int | None, model_version: str, provider: str | None, served_model: str | None,
                  prompt_tokens: int, completion_tokens: int, cache_read_tokens: int = 0, cache_creation_tokens: int = 0) -> None:
    """Add one call's tokens and estimated cost to the day's counter. Never raises: counting must not stop a request.
    A call is "priced" as decided by `is_priced`; anything else is counted as unpriced rather than as free."""
    try:
        from nortpole.db.models import ModelConfiguration
        from nortpole.llm.cost import _is_locally_hosted, compute_cost_cents
        from nortpole.governance.route_policy.enforce import check_route

        with get_session_with_current_tenant() as s:
            kind, provider_id, name = "unknown", -1, model_version
            if model_configuration_id is not None:
                row = s.get(ModelConfiguration, model_configuration_id)
                if row is not None:
                    kind, provider_id, name = check_route(s, model_configuration_id).kind, row.llm_provider_id, row.name
            input_cents, output_cents = compute_cost_cents(
                model=model_version, served_model=served_model, provider=provider, model_configuration_id=model_configuration_id,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cache_read_tokens=cache_read_tokens,
                cache_creation_tokens=cache_creation_tokens, db_session=s)
            cost = float(input_cents + output_cents)
            priced = is_priced(cost, kind, _is_locally_hosted(model_version, provider))
            values = dict(day=datetime.date.today(), route_kind=kind, provider_id=provider_id, model_name=name, calls=1,
                          prompt_tokens=max(int(prompt_tokens), 0), completion_tokens=max(int(completion_tokens), 0),
                          cost_cents=cost if priced else 0, unpriced_calls=0 if priced else 1)
            stmt = insert(NortPoleRouteTokens).values(**values)
            t = NortPoleRouteTokens
            stmt = stmt.on_conflict_do_update(constraint="uq_nortpole_route_tokens", set_={
                "calls": t.calls + 1, "prompt_tokens": t.prompt_tokens + values["prompt_tokens"],
                "completion_tokens": t.completion_tokens + values["completion_tokens"],
                "cost_cents": t.cost_cents + values["cost_cents"], "unpriced_calls": t.unpriced_calls + values["unpriced_calls"]})
            s.execute(stmt)
            s.commit()
    except Exception:  # noqa: BLE001
        logger.warning("route tokens were not recorded", exc_info=True)


def total_tokens(db, days: int):  # type: ignore[no-untyped-def]
    since = datetime.date.today() - datetime.timedelta(days=max(days, 1) - 1)
    t = NortPoleRouteTokens
    return (
        db.query(t.route_kind, t.model_name, func.sum(t.calls), func.sum(t.prompt_tokens), func.sum(t.completion_tokens),
                 func.sum(t.cost_cents), func.sum(t.unpriced_calls))
        .filter(t.day >= since).group_by(t.route_kind, t.model_name)
        .order_by(func.sum(t.prompt_tokens + t.completion_tokens).desc()).all()
    )
