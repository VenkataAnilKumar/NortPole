"""Apply redaction to a model request just before it is serialised and sent.

This sits in the model client's one entry point, so chat, tasks and anything
else that calls the client are covered, and the trace spans (which are built from
the serialised request) never see the original text. If the route cannot be
determined the request is treated as cloud (redacted); if redaction itself fails
the request is not sent."""

from __future__ import annotations

import datetime

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.models import Base
from evolvxsi.llm.models import (
    AssistantMessage,
    GenerationRequest,
    SystemMessage,
    TextContent,
    TextContentPart,
    ToolResult,
    UserMessage,
)
from evolvxsi.governance.redaction.redact import redact_text
from evolvxsi.governance.route_policy.policy import UNASSIGNED_KIND, load_policy
from evolvxsi.utils.logger import setup_logger

logger = setup_logger()


class EvolvXSIRedactionCount(Base):
    """How many items of each kind were replaced, by day and route kind. Counts only."""

    __tablename__ = "evolvxsi_redaction_count"
    __table_args__ = (UniqueConstraint("day", "route_kind", "data_kind", name="uq_evolvxsi_redaction_count"),)

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    route_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    data_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def _record(route_kind: str, counts: dict[str, int]) -> None:
    try:
        with get_session_with_current_tenant() as s:
            for kind, n in counts.items():
                stmt = insert(EvolvXSIRedactionCount).values(day=datetime.date.today(), route_kind=route_kind, data_kind=kind, items=n)
                s.execute(stmt.on_conflict_do_update(constraint="uq_evolvxsi_redaction_count",
                                                     set_={"items": EvolvXSIRedactionCount.items + n}))
            s.commit()
    except Exception:  # noqa: BLE001 - counting must not stop a request
        logger.warning("redaction counts were not recorded", exc_info=True)


def _route_kind(model_configuration_id: int | None) -> str:
    try:
        from evolvxsi.governance.route_policy.enforce import check_route

        with get_session_with_current_tenant() as s:
            return check_route(s, model_configuration_id).kind
    except Exception:  # noqa: BLE001 - unknown route: assume the least contained
        logger.warning("route kind unknown; treating the request as %s", UNASSIGNED_KIND, exc_info=True)
        return UNASSIGNED_KIND


def redact_request(request: GenerationRequest, model_configuration_id: int | None) -> GenerationRequest:
    kind = _route_kind(model_configuration_id)
    if kind not in load_policy().redact_route_kinds:
        return request
    total: dict[str, int] = {}

    def go(text: str) -> str:
        new, counts = redact_text(text)
        for k, n in counts.items():
            total[k] = total.get(k, 0) + n
        return new

    messages = []
    for m in request.messages:
        if isinstance(m, (SystemMessage, ToolResult)):
            m = m.model_copy(update={"content": go(m.content)})
        elif isinstance(m, UserMessage):
            if isinstance(m.content, str):
                m = m.model_copy(update={"content": go(m.content)})
            else:
                parts = [p.model_copy(update={"text": go(p.text)}) if isinstance(p, TextContentPart) else p for p in m.content]
                m = m.model_copy(update={"content": parts})
        elif isinstance(m, AssistantMessage):
            blocks = [b.model_copy(update={"text": go(b.text)}) if isinstance(b, TextContent) else b for b in m.content]
            m = m.model_copy(update={"content": blocks})
        messages.append(m)
    out = request.model_copy(update={"messages": messages, "system_prompt": go(request.system_prompt) if request.system_prompt else ""})
    if total:
        _record(kind, total)
    return out
