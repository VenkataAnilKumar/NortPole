"""Search chat and workflow records under their current access rules."""

from datetime import datetime
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import (
    String,
    and_,
    case,
    cast,
    column,
    func,
    literal,
    null,
    or_,
    select,
    tuple_,
    union_all,
)
from sqlalchemy.orm import Session

from nortpole.agents.models import RunStatus
from nortpole.auth.permissions import (
    has_global_permission,
    require_permission,
    resolve_effective_permissions,
)
from nortpole.configs.constants import MessageType
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission
from nortpole.db.models import ChatMessage, ChatSession, User
from nortpole.knowledge.knowledge_access.groups import group_names_for_user
from nortpole.redis.redis_pool import get_redis_client
from nortpole.server.api_key_usage import check_api_key_usage
from nortpole.server.features.search.workspace import CURSOR_TTL_SECONDS
from nortpole.work.workflow_schedules.models import (
    NortPoleWorkflowRun,
    NortPoleWorkflowSchedule,
    shared_schedule_clause,
)

router = APIRouter()


class ActivitySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2048)
    tab: Literal["chats", "workflows"]
    updated_since: datetime | None = None
    source: (
        Literal["schedule", "scheduled_run", "expense_review", "document_review"] | None
    ) = None
    status: str | None = Field(default=None, max_length=32)
    cursor: UUID | None = None
    page_size: int = Field(default=20, ge=1, le=300)


class ActivityResult(BaseModel):
    id: str
    title: str
    source: str
    status: str | None
    excerpt: str
    updated_at: datetime
    url: str


class ActivitySearchResponse(BaseModel):
    results: list[ActivityResult]
    next_cursor: UUID | None = None
    limited: bool = False
    lexical_only: bool = False


class ActivityContinuation(BaseModel):
    scope: str
    updated_at: datetime
    id: str


def _own_chat(user: User):
    return and_(
        ChatSession.user_id == user.id,
        ChatSession.deleted.is_(False),
        ChatSession.nortpolebot_flow.is_(False),
        ChatSession.spawned_by_message_id.is_(None),
        ChatSession.incognito_record_mode.is_(None),
    )


def _headline(text, query):
    return func.ts_headline(
        "english",
        text,
        query,
        "StartSel=__MATCH__, StopSel=__END__, MaxWords=45, MinWords=12",
    )


def _chat_results(user: User, query):
    # Pick one matching visible message per session. The title is a separate match.
    matches = (
        select(
            ChatMessage.chat_session_id.label("session_id"),
            ChatMessage.id.label("message_id"),
            ChatMessage.message.label("message"),
        )
        .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
        .where(
            _own_chat(user),
            ChatMessage.message_type.in_((MessageType.USER, MessageType.ASSISTANT)),
            column("message_tsv").op("@@")(query),
        )
        .distinct(ChatMessage.chat_session_id)
        .order_by(ChatMessage.chat_session_id, ChatMessage.id.desc())
        .subquery()
    )
    return (
        select(
            cast(ChatSession.id, String).label("id"),
            func.coalesce(
                func.nullif(ChatSession.description, ""), "Untitled chat"
            ).label("title"),
            literal("chat").label("source"),
            cast(null(), String).label("status"),
            _headline(
                func.coalesce(matches.c.message, ChatSession.description, ""), query
            ).label("excerpt"),
            ChatSession.time_updated.label("updated_at"),
            cast(ChatSession.id, String).label("target"),
            cast(matches.c.message_id, String).label("detail"),
        )
        .outerjoin(matches, matches.c.session_id == ChatSession.id)
        .where(
            _own_chat(user),
            or_(
                matches.c.message_id.is_not(None),
                column("description_tsv").op("@@")(query),
            ),
        )
        .subquery()
    )


def _workflow_results(user: User, db: Session, query, *, include_chat_reports: bool):
    schedule = NortPoleWorkflowSchedule
    run = NortPoleWorkflowRun
    shared = shared_schedule_clause(group_names_for_user(db, user.id))
    schedule_text = func.concat_ws(" ", schedule.name, schedule.title)
    definitions = select(
        (literal("schedule:") + cast(schedule.id, String)).label("id"),
        schedule.name.label("title"),
        literal("schedule").label("source"),
        schedule.state.label("status"),
        _headline(schedule_text, query).label("excerpt"),
        schedule.updated_at.label("updated_at"),
        cast(schedule.id, String).label("target"),
        cast(null(), String).label("detail"),
    ).where(
        or_(schedule.owner_id == user.id, shared),
        func.to_tsvector("english", schedule_text).op("@@")(query),
    )
    run_text = func.concat_ws(
        " ",
        schedule.name,
        schedule.title,
        func.replace(run.outcome, "_", " "),
        run.reason,
    )
    runs = (
        select(
            (literal("run:") + cast(run.id, String)).label("id"),
            schedule.name.label("title"),
            literal("scheduled_run").label("source"),
            run.outcome.label("status"),
            _headline(run_text, query).label("excerpt"),
            run.fired_at.label("updated_at"),
            cast(schedule.id, String).label("target"),
            cast(run.id, String).label("detail"),
        )
        .join(schedule, schedule.id == run.schedule_id)
        .where(
            schedule.owner_id == user.id,
            func.to_tsvector("english", run_text).op("@@")(query),
        )
    )

    # Chat-backed reports use the same owner and terminal-state boundaries as Runs.
    document = ChatMessage.document_review_needs_review.is_not(None)
    expense = ChatMessage.receipt_review_needs_review.is_not(None)
    review_type = case((document, "document_review"), else_="expense_review")
    review_label = case((document, "Document Review"), else_="Expense Review")
    review_text = func.concat_ws(
        " ", review_label, ChatSession.description, ChatMessage.message
    )
    needs_review = case(
        (document, ChatMessage.document_review_needs_review),
        else_=ChatMessage.receipt_review_needs_review,
    )
    review_status = case(
        (ChatMessage.response_status == RunStatus.CANCELLED, "stopped"),
        (ChatMessage.response_status != RunStatus.COMPLETE, "failed"),
        (needs_review.is_(True), "needs_review"),
        else_="complete",
    )
    reports = (
        select(
            (literal("review:") + cast(ChatMessage.id, String)).label("id"),
            review_label.label("title"),
            review_type.label("source"),
            review_status.label("status"),
            _headline(review_text, query).label("excerpt"),
            ChatMessage.time_sent.label("updated_at"),
            cast(ChatSession.id, String).label("target"),
            cast(ChatMessage.id, String).label("detail"),
        )
        .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
        .where(
            _own_chat(user),
            or_(document, expense),
            ChatMessage.response_status.in_(
                (
                    RunStatus.COMPLETE,
                    RunStatus.CANCELLED,
                    RunStatus.ERROR,
                    RunStatus.LIMIT,
                )
            ),
            func.to_tsvector("english", review_text).op("@@")(query),
        )
    )
    queries = [definitions, runs]
    if include_chat_reports:
        queries.append(reports)
    return union_all(*queries).subquery()


def _destination(
    source: str, status: str | None, target: str, detail: str | None
) -> str:
    if source in ("schedule", "scheduled_run"):
        location = f"/app/workflows/scheduled?schedule={target}"
        return f"{location}&run={detail}" if detail else location
    if source == "document_review" and status in ("complete", "needs_review"):
        return f"/app/workflows/runs?review={detail}"
    location = f"/app?chatId={target}"
    return f"{location}&message={detail}" if detail else location


@router.post("/workspace/activity", dependencies=[Depends(check_api_key_usage)])
def search_workspace_activity(
    request: ActivitySearchRequest,
    response: Response,
    http_request: Request,
    user: User = Depends(require_permission(Permission.READ_SEARCH)),
    db: Session = Depends(get_session),
) -> ActivitySearchResponse:
    response.headers["Cache-Control"] = "private, no-store"
    term = request.query.strip()
    if not term:
        raise HTTPException(status_code=422, detail="Enter a search query.")
    token_scopes: list[Permission] | None = getattr(  # ods: ignore[getattr]
        http_request.state, "token_scopes", None
    )
    token_grants = (
        resolve_effective_permissions({permission.value for permission in token_scopes})
        if token_scopes is not None
        else None
    )

    def can_open(permission: Permission) -> bool:
        return has_global_permission(user, permission) and (
            token_grants is None or permission.value in token_grants
        )

    can_read_chat = can_open(Permission.READ_CHAT)
    if not (
        can_read_chat if request.tab == "chats" else can_open(Permission.BASIC_ACCESS)
    ):
        raise HTTPException(
            status_code=403, detail="Search is unavailable for this section."
        )
    scope = sha256(
        f"{user.id}:{request.model_dump_json(exclude={'cursor', 'page_size'}, exclude_none=True)}".encode()
    ).hexdigest()
    store = get_redis_client()
    continuation = None
    if request.cursor:
        stored = store.get(f"activity-search:{request.cursor}")
        continuation = (
            ActivityContinuation.model_validate_json(stored) if stored else None
        )
        if continuation is None or continuation.scope != scope:
            raise HTTPException(
                status_code=410, detail="These results expired. Run the search again."
            )

    query = func.plainto_tsquery("english", term)
    matches = (
        _chat_results(user, query)
        if request.tab == "chats"
        else _workflow_results(user, db, query, include_chat_reports=can_read_chat)
    )
    statement = (
        select(matches)
        .order_by(matches.c.updated_at.desc(), matches.c.id.desc())
        .limit(request.page_size + 1)
    )
    if request.updated_since is not None:
        statement = statement.where(matches.c.updated_at >= request.updated_since)
    if request.source is not None:
        statement = statement.where(matches.c.source == request.source)
    if request.status is not None:
        statement = statement.where(matches.c.status == request.status)
    if continuation:
        statement = statement.where(
            tuple_(matches.c.updated_at, matches.c.id)
            < (continuation.updated_at, continuation.id)
        )

    rows = db.execute(statement).all()
    next_cursor = None
    if len(rows) > request.page_size:
        tail = rows[request.page_size - 1]
        next_cursor = uuid4()
        state = ActivityContinuation(
            scope=scope, updated_at=tail.updated_at, id=tail.id
        )
        store.set(
            f"activity-search:{next_cursor}",
            state.model_dump_json(),
            ex=CURSOR_TTL_SECONDS,
        )
    return ActivitySearchResponse(
        next_cursor=next_cursor,
        results=[
            ActivityResult(
                id=row.id,
                title=row.title,
                source=row.source,
                status=row.status,
                excerpt=" ".join(
                    row.excerpt.replace("__MATCH__", "").replace("__END__", "").split()
                )[:420],
                updated_at=row.updated_at,
                url=_destination(row.source, row.status, row.target, row.detail),
            )
            for row in rows[: request.page_size]
        ],
    )
