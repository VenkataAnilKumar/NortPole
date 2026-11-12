"""Count the model requests that were allowed, by day, route, model, data class
and purpose. Counters only: no person, no prompt, no text. Blocked requests are
in the audit log with the person; this answers "what actually ran where".
Counts are requests, not tokens or money: the token count is not known when the
route is checked, so no spend figure is claimed."""

from __future__ import annotations

import datetime

from sqlalchemy import Date, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.models import Base
from evolvxsi.utils.logger import setup_logger

logger = setup_logger()

class EvolvXSIRouteUsage(Base):
    __tablename__ = "evolvxsi_route_usage"
    __table_args__ = (
        UniqueConstraint("day", "route_kind", "provider_id", "model_name", "data_class", "purpose", name="uq_evolvxsi_route_usage"),
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
            stmt = insert(EvolvXSIRouteUsage).values(**values)
            stmt = stmt.on_conflict_do_update(constraint="uq_evolvxsi_route_usage",
                                              set_={"requests": EvolvXSIRouteUsage.requests + 1})
            s.execute(stmt)
            s.commit()
    except Exception:  # noqa: BLE001
        logger.warning("route usage was not recorded", exc_info=True)


def total(db, days: int):  # type: ignore[no-untyped-def]
    since = datetime.date.today() - datetime.timedelta(days=max(days, 1) - 1)
    q = (
        db.query(EvolvXSIRouteUsage.route_kind, EvolvXSIRouteUsage.model_name, EvolvXSIRouteUsage.data_class,
                 EvolvXSIRouteUsage.purpose, func.sum(EvolvXSIRouteUsage.requests))
        .filter(EvolvXSIRouteUsage.day >= since)
        .group_by(EvolvXSIRouteUsage.route_kind, EvolvXSIRouteUsage.model_name, EvolvXSIRouteUsage.data_class, EvolvXSIRouteUsage.purpose)
        .order_by(func.sum(EvolvXSIRouteUsage.requests).desc())
    )
    return q.all()
