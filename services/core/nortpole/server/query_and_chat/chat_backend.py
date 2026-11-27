import datetime
import json
import time
from collections.abc import Generator
from concurrent.futures import Future
from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import String, cast, literal, or_, select, tuple_, union_all
from sqlalchemy.orm import Session, aliased

from nortpole.access.access import user_can_access_chat_file
from nortpole.agents.models import RunStatus
from nortpole.auth.api_key import get_hashed_api_key_from_request
from nortpole.auth.pat import get_hashed_pat_from_request
from nortpole.auth.permissions import has_global_permission, require_permission, resolve_effective_permissions
from nortpole.auth.users import current_chat_accessible_user
from nortpole.background.task_utils import enqueue_user_file_deletes
from nortpole.cache.factory import get_cache_backend
from nortpole.chat.chat_processing_checker import (
    ADMISSION_CACHE_TIMEOUT_S,
    get_processing_stream_id,
    is_chat_session_processing,
)
from nortpole.chat.chat_utils import (
    convert_chat_history_basic,
    create_chat_session_from_request,
)
from nortpole.chat.incognito import (
    delete_incognito_generated_files,
    incognito_allowed_for_user,
)
from nortpole.chat.incognito_context import teardown_incognito_session
from nortpole.chat.models import ChatFullResponse, ChatResponseOutcome, CreateChatSessionResponse
from nortpole.chat.process_message import (
    handle_multi_model_stream,
    handle_stream_message_objects,
    run_chat_turn,
)
from nortpole.chat.prompt_utils import get_default_base_system_prompt
from nortpole.chat.stop_signal_checker import request_stop
from nortpole.chat.stream_buffer import has_stream_buffer, read_stream_chunks
from nortpole.configs.app_configs import WEB_DOMAIN
from nortpole.configs.chat_configs import (
    CHAT_HEARTBEAT_INTERVAL_S,
    CHAT_RESUME_POLL_INTERVAL_S,
    HARD_DELETE_CHATS,
)
from nortpole.configs.constants import (
    PUBLIC_API_TAGS,
    MessageType,
    MilestoneRecordType,
)
from nortpole.configs.model_configs import LITELLM_PASS_THROUGH_HEADERS
from nortpole.configs.tool_configs import CUSTOM_TOOL_PASS_THROUGH_HEADERS
from nortpole.db.chat import (
    add_chats_to_session_from_slack_thread,
    create_chat_history_chain,
    delete_all_chat_sessions_for_user,
    delete_chat_session,
    duplicate_chat_session_for_user_from_slack,
    get_chat_message,
    get_chat_message_page_ids,
    get_chat_messages_by_session,
    get_chat_session_by_id,
    get_chat_sessions_by_user,
    get_incognito_session_ids_for_user,
    set_as_latest_chat_message,
    set_preferred_response,
    translate_db_message_to_chat_message_detail,
    update_chat_session,
)
from nortpole.db.chat_search import search_chat_sessions
from nortpole.db.engine.sql_engine import get_session, get_session_with_current_tenant
from nortpole.db.enums import LLMModelFlowType, Permission, record_mode_persists_content
from nortpole.db.feedback import create_chat_message_feedback, remove_chat_message_feedback
from nortpole.db.incognito import (
    is_incognito_teardown_target,
    mark_incognito_user_files_deleting,
)
from nortpole.db.models import AgentRelease, ChatMessage, ChatSession, ChatSessionSharedStatus, Persona, User
from nortpole.chat.agent_pilots import AgentPilotInput, describe_pilot
from nortpole.chat.agent_preview import require_preview_access
from nortpole.chat.agent_releases import pinned_agent_release
from nortpole.db.persona import get_persona_by_id, user_can_access_persona
from nortpole.db.usage import UsageType, increment_usage
from nortpole.db.user_file import get_file_id_by_user_file_id
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.file_store.file_store import get_default_file_store
from nortpole.file_store.serving import (
    ATTACHMENT_SAFE_MIME_TYPES,
    RESPONSE_POLICY_VERSION,
    ensure_filename_extension,
    resolve_inline_disposition,
)
from nortpole.llm.constants import LlmProviderNames
from nortpole.llm.factory import (
    get_default_utility_llm,
    get_llm_for_persona,
    get_llm_token_counter,
)
from nortpole.llm.models import (
    USER_SELECTABLE_REASONING_EFFORTS,
    ReasoningEffort,
    parse_user_selectable_reasoning_effort,
)
from nortpole.llm.override_models import LLMOverride
from nortpole.secondary_llm_flows.chat_session_naming import (
    DEFAULT_CHAT_SESSION_NAME,
    generate_chat_session_name,
    get_fallback_chat_session_name,
)
from nortpole.server.api_key_usage import check_api_key_usage
from nortpole.server.middleware.rate_limiting import get_feedback_rate_limiters
from nortpole.server.query_and_chat.chat_utils import (
    is_spreadsheet_mime_type,
    parse_spreadsheet_for_preview,
)
from nortpole.server.query_and_chat.models import (
    ChatFeedbackRequest,
    ChatMessageIdentifier,
    ChatRenameRequest,
    ChatSearchResponse,
    ChatSessionCreationRequest,
    ChatSessionDetailResponse,
    ChatSessionDetails,
    ChatSessionGroup,
    ChatSessionProcessingStatus,
    ChatSessionsResponse,
    ChatSessionSummary,
    ChatSessionUpdateRequest,
    CurrentStreamInfo,
    MessageOrigin,
    RenameChatSessionResponse,
    SendMessageRequest,
    SetPreferredResponseRequest,
    StopChatResponse,
    UpdateChatSessionReasoningRequest,
    UpdateChatSessionTemperatureRequest,
    UpdateChatSessionThreadRequest,
)
from nortpole.server.query_and_chat.session_loading import (
    load_session_tools,
    translate_assistant_message_to_packets,
)
from nortpole.server.query_and_chat.streaming_models import (
    Packet,
    StreamCursor,
    heartbeat_packet,
)
from nortpole.server.query_and_chat.token_limit import (
    check_model_spend_limits,
    check_token_rate_limits,
)
from nortpole.server.usage_limits import (
    check_llm_cost_limit_for_provider,
    check_usage_and_raise,
    is_usage_limits_enabled,
)
from nortpole.server.utils import get_json_line
from nortpole.tracing.framework.create import ChatTraceMetadata, ensure_trace
from nortpole.utils.headers import get_relevant_headers
from nortpole.utils.logger import setup_logger
from nortpole.utils.telemetry import mt_cloud_telemetry
from nortpole.work.document_reviews import open_finding_counts, router as document_reviews_router
from nortpole.work.tasks.models import NortPoleTask
from nortpole.work.workflow_schedules.recovery import can_retry
from nortpole.work.workflow_schedules.runner import INTERRUPTED_AFTER, effective_outcome
from nortpole.work.workflow_schedules.models import (
    DriveRunSource,
    NortPoleWorkflowRun,
    NortPoleWorkflowSchedule,
)
from shared_configs.contextvars import get_current_tenant_id

logger = setup_logger()

# Largest page a client can ask of `get-chat-session`.
MAX_CHAT_SESSION_PAGE_SIZE = 200

router = APIRouter(prefix="/chat")
router.include_router(document_reviews_router)


def _get_available_tokens_for_persona(
    persona: Persona,
    db_session: Session,
    user: User,
    llm_override: LLMOverride | None = None,
) -> int:
    def _get_non_reserved_input_tokens(
        model_max_input_tokens: int,
        system_and_agent_prompt_tokens: int,
        num_tools: int,
        token_reserved_per_tool: int = 256,
        # Estimating for a long user input message, hard to know ahead of time
        default_reserved_tokens: int = 2000,
    ) -> int:
        return (
            model_max_input_tokens
            - system_and_agent_prompt_tokens
            - num_tools * token_reserved_per_tool
            - default_reserved_tokens
        )

    llm = get_llm_for_persona(persona=persona, user=user, llm_override=llm_override)
    token_counter = get_llm_token_counter(llm)

    if persona.replace_base_system_prompt and persona.system_prompt:
        # User has opted to replace the base system prompt entirely
        combined_prompt_tokens = token_counter(persona.system_prompt)
    else:
        # Default behavior: prepend custom prompt to base system prompt
        system_prompt = get_default_base_system_prompt(db_session)
        agent_prompt = persona.system_prompt + " " if persona.system_prompt else ""
        combined_prompt_tokens = token_counter(agent_prompt + system_prompt)

    return _get_non_reserved_input_tokens(
        model_max_input_tokens=llm.config.max_input_tokens,
        system_and_agent_prompt_tokens=combined_prompt_tokens,
        num_tools=len(persona.tools),
    )


class ExpenseReviewRun(BaseModel):
    id: int
    chat_session_id: UUID
    file_name: str | None
    created_at: datetime.datetime
    status: Literal["complete", "needs_review", "stopped", "failed", "running", "interrupted"]
    drive_source: DriveRunSource | None = None
    workflow: Literal["expense_review", "document_review"] = "expense_review"
    open_findings: int | None = None
    revision_of: int | None = None


class SkippedExpenseReview(BaseModel):
    id: UUID
    name: str
    created_at: datetime.datetime
    reason: str | None


class ExpenseReviewRunPage(BaseModel):
    runs: list[ExpenseReviewRun]
    next_before_id: int | None = None
    recent_skips: list[SkippedExpenseReview]


@router.get("/expense-review-runs")
def list_expense_review_runs(
    user: User = Depends(require_permission(Permission.READ_CHAT)),
    db_session: Session = Depends(get_session),
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    before_id: Annotated[int | None, Query(gt=0)] = None,
) -> ExpenseReviewRunPage:
    """List completed or stopped Expense Review responses in the caller's chat history."""
    return _review_runs(user, db_session, page_size, before_id, include_document=False)


@router.get("/workflow-runs")
def list_workflow_runs(
    user: User = Depends(require_permission(Permission.READ_CHAT)),
    db_session: Session = Depends(get_session),
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    before_id: Annotated[int | None, Query(gt=0)] = None,
) -> ExpenseReviewRunPage:
    return _review_runs(user, db_session, page_size, before_id, include_document=True)


def _review_runs(
    user: User, db_session: Session, page_size: int, before_id: int | None, *,
    include_document: bool, response_ids: list[int] | None = None,
) -> ExpenseReviewRunPage:
    parent = aliased(ChatMessage)
    expense = ChatMessage.receipt_review_needs_review.is_not(None)
    document = ChatMessage.document_review_needs_review.is_not(None)
    stmt = (
        select(
            ChatMessage.id,
            ChatMessage.chat_session_id,
            ChatMessage.time_sent,
            ChatMessage.response_status,
            ChatMessage.receipt_review_needs_review,
            ChatMessage.document_review_needs_review,
            ChatMessage.document_review_report,
            parent.files,
            NortPoleWorkflowRun.drive_source,
        )
        .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
        .outerjoin(
            NortPoleWorkflowRun,
            NortPoleWorkflowRun.chat_session_id == ChatMessage.chat_session_id,
        )
        .outerjoin(
            parent,
            (parent.id == ChatMessage.parent_message_id)
            & (parent.chat_session_id == ChatMessage.chat_session_id),
        )
        .where(
            ChatSession.user_id == user.id,
            ChatSession.deleted.is_(False),
            ChatSession.incognito_record_mode.is_(None),
            or_(expense, document) if include_document else expense,
        )
        .order_by(ChatMessage.id.desc())
        .limit(page_size + 1)
    )
    if response_ids is not None:
        stmt = stmt.where(ChatMessage.id.in_(response_ids))
    else:
        stmt = stmt.where(ChatMessage.response_status.in_(
            (RunStatus.COMPLETE, RunStatus.CANCELLED, RunStatus.ERROR, RunStatus.LIMIT)
        ))
    if before_id is not None:
        stmt = stmt.where(ChatMessage.id < before_id)
    rows = db_session.execute(stmt).all()
    counts = open_finding_counts(db_session, {
        row.id: row.document_review_report
        for row in rows[:page_size]
        if row.document_review_report is not None and row.response_status == RunStatus.COMPLETE
    })
    runs: list[ExpenseReviewRun] = []
    for response_id, session_id, when, outcome, expense_review, document_review, report, files, drive_source in rows[:page_size]:
        status: Literal["complete", "needs_review", "stopped", "failed", "running", "interrupted"]
        open_findings = counts.get(response_id)
        if outcome == RunStatus.COMPLETE:
            needs_review = (expense_review or document_review) if open_findings is None else bool(open_findings)
            status = "needs_review" if needs_review else "complete"
        elif outcome == RunStatus.CANCELLED:
            status = "stopped"
        elif outcome is None or not outcome.is_terminal:
            status = "interrupted" if when + INTERRUPTED_AFTER <= datetime.datetime.now(datetime.timezone.utc) else "running"
        else:
            status = "failed"
        runs.append(ExpenseReviewRun(
            id=response_id,
            chat_session_id=session_id,
            file_name=files[0].get("name") if files else None,
            created_at=when,
            status=status,
            drive_source=drive_source if document_review is None else None,
            workflow="expense_review" if document_review is None else "document_review",
            open_findings=open_findings,
            revision_of=((report or {}).get("revision") or {}).get("previous_id"),
        ))
    skips = []
    if before_id is None and response_ids is None:
        skipped_rows = db_session.execute(
            select(NortPoleWorkflowRun.id, NortPoleWorkflowSchedule.name,
                   NortPoleWorkflowRun.fired_at, NortPoleWorkflowRun.reason)
            .join(NortPoleWorkflowSchedule)
            .where(NortPoleWorkflowSchedule.owner_id == user.id,
                   NortPoleWorkflowRun.outcome.in_(("no_new_csv", "drive_skipped")))
            .order_by(NortPoleWorkflowRun.fired_at.desc())
            .limit(5)
        )
        skips = [
            SkippedExpenseReview(id=run_id, name=name, created_at=when, reason=reason)
            for run_id, name, when, reason in skipped_rows
        ]
    return ExpenseReviewRunPage(
        runs=runs,
        next_before_id=runs[-1].id if len(rows) > page_size else None,
        recent_skips=skips,
    )


class ScheduledRunEntry(BaseModel):
    id: UUID
    schedule_id: UUID
    name: str
    created_at: datetime.datetime
    trigger: str | None
    schedule_version: int | None
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    outcome: str
    reason: str | None
    task_id: UUID | None
    task_state: str | None
    chat_session_id: UUID | None
    chat_message_id: int | None = None
    file_name: str | None = None
    drive_source: DriveRunSource | None
    expense_review: bool
    retry_of_id: UUID | None = None
    retry_id: UUID | None = None
    can_retry: bool = False


class WorkflowRunCursor(BaseModel):
    at: datetime.datetime
    key: str


class WorkflowRunFeed(BaseModel):
    runs: list[ScheduledRunEntry | ExpenseReviewRun]
    next_before: WorkflowRunCursor | None = None


@router.get("/workflow-run-feed")
def workflow_run_feed(
    user: User = Depends(require_permission(Permission.READ_CHAT)),
    db_session: Session = Depends(get_session),
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    before_at: datetime.datetime | None = None,
    before_key: Annotated[str | None, Query(max_length=50)] = None,
    include_run: UUID | None = None,
) -> WorkflowRunFeed:
    """Merge private schedule runs and direct Chat reviews with one stable cursor."""
    run = NortPoleWorkflowRun
    schedule = NortPoleWorkflowSchedule
    message = ChatMessage
    scheduled_keys = select(
        (literal("run:") + cast(run.id, String)).label("key"), run.fired_at.label("at"),
    ).join(schedule, schedule.id == run.schedule_id).where(schedule.owner_id == user.id)
    review_keys = select(
        (literal("review:") + cast(message.id, String)).label("key"), message.time_sent.label("at"),
    ).join(ChatSession, ChatSession.id == message.chat_session_id).where(
        ChatSession.user_id == user.id,
        ChatSession.deleted.is_(False),
        ChatSession.incognito_record_mode.is_(None),
        or_(message.receipt_review_needs_review.is_not(None), message.document_review_needs_review.is_not(None)),
        ~select(run.id).where(run.chat_session_id == message.chat_session_id).exists(),
    )
    keys = union_all(scheduled_keys, review_keys).subquery()
    selection = select(keys).order_by(keys.c.at.desc(), keys.c.key.desc()).limit(page_size + 1)
    if before_at is not None and before_key is not None:
        selection = selection.where(tuple_(keys.c.at, keys.c.key) < tuple_(before_at, before_key))
    rows = db_session.execute(selection).all()
    page = rows[:page_size]
    order = [row.key for row in page]
    if include_run and f"run:{include_run}" not in order:
        order.insert(0, f"run:{include_run}")

    run_ids = [UUID(key.removeprefix("run:")) for key in order if key.startswith("run:")]
    review_ids = [int(key.removeprefix("review:")) for key in order if key.startswith("review:")]
    entries: dict[str, ScheduledRunEntry | ExpenseReviewRun] = {}
    if run_ids:
        now = datetime.datetime.now(datetime.timezone.utc)
        retry = aliased(NortPoleWorkflowRun)
        for record, definition, task, chat, retry_id in db_session.execute(
            select(run, schedule, NortPoleTask, ChatSession, retry.id)
            .join(schedule, schedule.id == run.schedule_id)
            .outerjoin(retry, (retry.retry_of_id == run.id) & (retry.schedule_id == schedule.id))
            .outerjoin(NortPoleTask, (NortPoleTask.id == run.task_id) & (NortPoleTask.owner_id == user.id))
            .outerjoin(ChatSession, (
                (ChatSession.id == run.chat_session_id) & (ChatSession.user_id == user.id)
                & ChatSession.deleted.is_(False) & ChatSession.incognito_record_mode.is_(None)
            ))
            .where(schedule.owner_id == user.id, run.id.in_(run_ids))
        ):
            entries[f"run:{record.id}"] = ScheduledRunEntry(
                id=record.id, schedule_id=definition.id, name=definition.name, created_at=record.fired_at,
                trigger=record.trigger, schedule_version=record.schedule_version, started_at=record.started_at,
                completed_at=record.completed_at, outcome=effective_outcome(record, now), reason=record.reason,
                task_id=task.id if task else None, task_state=task.state if task else None,
                chat_session_id=chat.id if chat else None, drive_source=record.drive_source,
                chat_message_id=record.chat_result_id if chat else None,
                expense_review=definition.expense_review is not None,
                retry_of_id=record.retry_of_id, retry_id=retry_id,
                can_retry=retry_id is None and can_retry(db_session, definition, record, task),
            )
        scheduled = [entry for entry in entries.values() if isinstance(entry, ScheduledRunEntry) and entry.chat_session_id]
        if scheduled:
            parent = aliased(ChatMessage)
            results = {
                chat_id: (response_id, files[0].get("name") if files else None)
                for chat_id, response_id, files in db_session.execute(
                    select(message.chat_session_id, message.id, parent.files)
                    .outerjoin(parent, (parent.id == message.parent_message_id) & (parent.chat_session_id == message.chat_session_id))
                    .where(
                        message.chat_session_id.in_([entry.chat_session_id for entry in scheduled]),
                        message.receipt_review_needs_review.is_not(None),
                    )
                    .distinct(message.chat_session_id)
                    .order_by(message.chat_session_id, message.id)
                )
            }
            for entry in scheduled:
                message_id, file_name = results.get(entry.chat_session_id, (None, None))
                if entry.chat_message_id is None or entry.chat_message_id == message_id:
                    entry.chat_message_id, entry.file_name = message_id, file_name
    if review_ids:
        reviews = _review_runs(user, db_session, page_size, None, include_document=True, response_ids=review_ids)
        entries.update({f"review:{review.id}": review for review in reviews.runs})
    return WorkflowRunFeed(
        runs=[entries[key] for key in order if key in entries],
        next_before=WorkflowRunCursor(at=page[-1].at, key=page[-1].key) if len(rows) > page_size else None,
    )


@router.get("/get-user-chat-sessions", tags=PUBLIC_API_TAGS)
def get_user_chat_sessions(
    user: User = Depends(require_permission(Permission.READ_CHAT)),
    db_session: Session = Depends(get_session),
    project_id: int | None = None,
    only_non_project_chats: bool = True,
    include_failed_chats: bool = False,
    page_size: int = Query(default=50, ge=1, le=100),
    before: str | None = Query(default=None),
) -> ChatSessionsResponse:
    user_id = user.id

    try:
        before_dt = (
            datetime.datetime.fromisoformat(before) if before is not None else None
        )
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid 'before' timestamp format")

    try:
        # Fetch one extra to determine if there are more results
        chat_sessions = get_chat_sessions_by_user(
            user_id=user_id,
            deleted=False,
            db_session=db_session,
            project_id=project_id,
            only_non_project_chats=only_non_project_chats,
            include_failed_chats=include_failed_chats,
            # The owner's own history is the one surface incognito hides from.
            exclude_incognito=True,
            limit=page_size + 1,
            before=before_dt,
        )

    except ValueError:
        raise ValueError("Chat session does not exist or has been deleted")

    has_more = len(chat_sessions) > page_size
    chat_sessions = chat_sessions[:page_size]

    return ChatSessionsResponse(
        sessions=[
            ChatSessionDetails(
                id=chat.id,
                name=chat.description,
                persona_id=chat.persona_id,
                time_created=chat.time_created.isoformat(),
                time_updated=chat.time_updated.isoformat(),
                shared_status=chat.shared_status,
                current_alternate_model=chat.current_alternate_model,
                current_temperature_override=chat.temperature_override,
                current_reasoning_effort_override=chat.reasoning_effort_override,
                agent_preview_name=chat.agent_preview.name if chat.agent_preview else None,
            )
            for chat in chat_sessions
        ],
        has_more=has_more,
    )


@router.put("/update-chat-session-temperature")
def update_chat_session_temperature(
    update_thread_req: UpdateChatSessionTemperatureRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    chat_session = get_chat_session_by_id(
        chat_session_id=update_thread_req.chat_session_id,
        user_id=user.id,
        db_session=db_session,
    )

    # Validate temperature_override
    if update_thread_req.temperature_override is not None:
        if (
            update_thread_req.temperature_override < 0
            or update_thread_req.temperature_override > 2
        ):
            raise HTTPException(
                status_code=400, detail="Temperature must be between 0 and 2"
            )

        # Additional check for Anthropic models
        if (
            chat_session.current_alternate_model
            and LlmProviderNames.ANTHROPIC
            in chat_session.current_alternate_model.lower()
        ):
            if update_thread_req.temperature_override > 1:
                raise HTTPException(
                    status_code=400,
                    detail="Temperature for Anthropic models must be between 0 and 1",
                )

    chat_session.temperature_override = update_thread_req.temperature_override

    db_session.add(chat_session)
    db_session.commit()


@router.put("/update-chat-session-reasoning")
def update_chat_session_reasoning(
    update_thread_req: UpdateChatSessionReasoningRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    chat_session = get_chat_session_by_id(
        chat_session_id=update_thread_req.chat_session_id,
        user_id=user.id,
        db_session=db_session,
    )

    # NULL clears the override. Any set value must be a user-selectable effort.
    reasoning_effort: ReasoningEffort | None = None
    if update_thread_req.reasoning_effort_override is not None:
        try:
            reasoning_effort = parse_user_selectable_reasoning_effort(
                update_thread_req.reasoning_effort_override
            )
        except ValueError:
            raise NortPoleError(
                NortPoleErrorCode.INVALID_INPUT,
                "reasoning_effort_override must be one of: "
                + ", ".join(
                    effort.value
                    for effort in ReasoningEffort
                    if effort in USER_SELECTABLE_REASONING_EFFORTS
                ),
            )

    chat_session.reasoning_effort_override = reasoning_effort
    db_session.add(chat_session)
    db_session.commit()


@router.put("/update-chat-session-model")
def update_chat_session_model(
    update_thread_req: UpdateChatSessionThreadRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    chat_session = get_chat_session_by_id(
        chat_session_id=update_thread_req.chat_session_id,
        user_id=user.id,
        db_session=db_session,
    )
    chat_session.current_alternate_model = update_thread_req.new_alternate_model

    db_session.add(chat_session)
    db_session.commit()


@router.get("/get-chat-session/{session_id}", tags=PUBLIC_API_TAGS)
def get_chat_session(
    session_id: UUID,
    is_shared: bool = False,
    include_deleted: bool = False,
    # In `Annotated`, so a direct call (as in tests) gets the plain default.
    limit: Annotated[
        int | None,
        Query(
            ge=1,
            le=MAX_CHAT_SESSION_PAGE_SIZE,
            description=(
                "Return one page of the current branch: its last `limit` "
                "messages and their children. `has_older_messages` tells "
                "whether the branch has messages before the page. Without it, "
                "every message on every branch is returned."
            ),
        ),
    ] = None,
    before_message_id: Annotated[
        int | None,
        Query(
            description=(
                "With `limit`, return the page that ends before this message. "
                "Pass the oldest loaded message to load the next older page."
            ),
        ),
    ] = None,
    user: User = Depends(
        require_permission(Permission.READ_CHAT, allow_anonymous=True)
    ),
    db_session: Session = Depends(get_session),
) -> ChatSessionDetailResponse:
    user_id = user.id
    try:
        chat_session = get_chat_session_by_id(
            chat_session_id=session_id,
            user_id=user_id,
            db_session=db_session,
            is_shared=is_shared,
            include_deleted=include_deleted,
        )
    except ValueError:
        try:
            # If we failed to get a chat session, try to retrieve the session with
            # less restrictive filters in order to identify what exactly mismatched
            # so we can bubble up an accurate error code andmessage.
            existing_chat_session = get_chat_session_by_id(
                chat_session_id=session_id,
                user_id=None,
                db_session=db_session,
                is_shared=False,
                include_deleted=True,
            )
        except ValueError:
            raise HTTPException(status_code=404, detail="Chat session not found")

        if not include_deleted and existing_chat_session.deleted:
            raise HTTPException(status_code=404, detail="Chat session has been deleted")

        if is_shared:
            if existing_chat_session.shared_status != ChatSessionSharedStatus.PUBLIC:
                raise HTTPException(
                    status_code=403, detail="Chat session is not shared"
                )
        elif user_id is not None and existing_chat_session.user_id not in (
            user_id,
            None,
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        raise HTTPException(status_code=404, detail="Chat session not found")

    # for chat-seeding: if the session is unassigned, assign it now. This is done here
    # to avoid another back and forth between FE -> BE before starting the first
    # message generation
    if chat_session.user_id is None and user_id is not None:
        chat_session.user_id = user_id
        db_session.commit()

    page_message_ids: set[int] | None = None
    has_older_messages = False
    if limit is not None:
        page_message_ids, has_older_messages = get_chat_message_page_ids(
            chat_session_id=session_id,
            db_session=db_session,
            limit=limit,
            before_message_id=before_message_id,
        )

    session_messages = get_chat_messages_by_session(
        chat_session_id=session_id,
        user_id=user_id,
        db_session=db_session,
        message_ids=page_message_ids,
        # we already did a permission check above with the call to
        # `get_chat_session_by_id`, so we can skip it here
        skip_permission_check=True,
        # we need the tool call objs anyways, so just fetch them in a single call
        prefetch_top_two_level_tool_calls=True,
        prefetch_message_details=True,
        # the replay builds search and fetch packets from these
        prefetch_tool_call_search_docs=True,
    )

    # Convert messages to ChatMessageDetail format
    chat_message_details = [
        translate_db_message_to_chat_message_detail(msg) for msg in session_messages
    ]

    current_stream: CurrentStreamInfo | None = None
    is_processing = True
    try:
        cache = get_cache_backend(operation_timeout_s=ADMISSION_CACHE_TIMEOUT_S)
        is_processing = is_chat_session_processing(session_id, cache)
        stream_id = get_processing_stream_id(session_id, cache)
        if stream_id is not None:
            current_stream = CurrentStreamInfo(stream_id=stream_id)
    except Exception:
        is_processing = True
        logger.exception(
            "An error occurred while checking if the chat session is processing"
        )

    # Every assistant message might have a set of tool calls associated with it, these need to be replayed back for the frontend
    # Each list is the set of tool calls for the given assistant message.
    tools_by_id = load_session_tools(session_messages, db_session)
    replay_packet_lists: list[list[Packet]] = [
        translate_assistant_message_to_packets(
            chat_message=msg, tools_by_id=tools_by_id, db_session=db_session
        )
        for msg in session_messages
        if msg.message_type == MessageType.ASSISTANT
    ]

    release = db_session.get(AgentRelease, chat_session.agent_release_id) if chat_session.agent_release_id is not None else None
    return ChatSessionDetailResponse(
        chat_session_id=session_id,
        description=chat_session.description,
        persona_id=chat_session.persona_id,
        persona_name=chat_session.persona.name if chat_session.persona else None,
        personal_icon_name=chat_session.persona.icon_name,
        current_alternate_model=chat_session.current_alternate_model,
        messages=chat_message_details,
        time_created=chat_session.time_created,
        shared_status=chat_session.shared_status,
        current_temperature_override=chat_session.temperature_override,
        current_reasoning_effort_override=chat_session.reasoning_effort_override,
        deleted=chat_session.deleted,
        owner_name=chat_session.user.personal_name if chat_session.user else None,
        # Packets are now directly serialized as Packet Pydantic models
        packets=replay_packet_lists,
        current_stream=current_stream,
        is_processing=is_processing,
        incognito=chat_session.incognito_record_mode is not None,
        agent_preview_name=chat_session.agent_preview.name if chat_session.agent_preview else None,
        agent_release_version=release.version if release is not None else None,
        has_older_messages=has_older_messages,
    )


@router.get("/pilot-input/{session_id}")
def get_chat_pilot_input(
    session_id: UUID,
    user: User = Depends(require_permission(Permission.READ_CHAT)),
    db_session: Session = Depends(get_session),
) -> AgentPilotInput | None:
    try:
        chat = get_chat_session_by_id(session_id, user.id, db_session)
    except ValueError as exc:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Chat unavailable.") from exc
    if chat.user_id != user.id:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Chat unavailable.")
    if chat.agent_preview is not None:
        if chat.agent_preview.pilot is None:
            return None
        require_preview_access(chat.persona, user, db_session)
        return describe_pilot(chat.agent_preview, user, db_session)
    if chat.agent_release_id is None:
        return None
    if chat.persona_id is None or not user_can_access_persona(db_session, chat.persona_id, user):
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Agent unavailable.")
    release = pinned_agent_release(chat, db_session)
    return describe_pilot(release.configuration, user, db_session) if release else None


@router.post("/create-chat-session", tags=PUBLIC_API_TAGS)
def create_new_chat_session(
    chat_session_creation_request: ChatSessionCreationRequest,
    user: User = Depends(
        require_permission(Permission.WRITE_CHAT, allow_anonymous=True)
    ),
    db_session: Session = Depends(get_session),
) -> CreateChatSessionResponse:
    try:
        new_chat_session = create_chat_session_from_request(
            chat_session_request=chat_session_creation_request,
            user=user,
            db_session=db_session,
        )
    except NortPoleError:
        # Carries its own status and detail (e.g. incognito refused).
        raise
    except ValueError as e:
        # Project or persona access denied
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=400, detail="Invalid Persona provided.")

    release = (
        db_session.get(AgentRelease, new_chat_session.agent_release_id)
        if new_chat_session.agent_release_id is not None else None
    )
    return CreateChatSessionResponse(
        chat_session_id=new_chat_session.id,
        incognito=new_chat_session.incognito_record_mode is not None,
        agent_release_version=release.version if release is not None else None,
    )


def _generate_or_fallback_chat_session_name(
    chat_history: list[ChatMessage],
    request: Request,
    user: User,
    chat_session_id: UUID,
    persona: Persona | None,
    llm_override: LLMOverride | None,
) -> str:
    user_id = user.id
    fallback_name = get_fallback_chat_session_name(chat_history)
    max_tokens_for_naming = 3000

    try:
        check_token_rate_limits(user)
        additional_headers = get_relevant_headers(
            request.headers, LITELLM_PASS_THROUGH_HEADERS
        )
        llm = get_default_utility_llm(
            additional_headers=additional_headers,
            flow_type=LLMModelFlowType.CHAT_NAMING,
        )
        if llm is None:
            llm = get_llm_for_persona(
                persona=persona,
                user=user,
                llm_override=llm_override,
                additional_headers=additional_headers,
            )
            with get_session_with_current_tenant() as db_session:
                check_llm_cost_limit_for_provider(
                    db_session=db_session,
                    tenant_id=get_current_tenant_id(),
                    llm_provider_api_key=llm.config.api_key,
                )
            check_model_spend_limits(user, llm.config.model_configuration_id)

        token_counter = get_llm_token_counter(llm)
        simple_chat_history = convert_chat_history_basic(
            chat_history=chat_history,
            token_counter=token_counter,
            max_individual_message_tokens=max_tokens_for_naming,
            max_total_tokens=max_tokens_for_naming,
        )
        with ensure_trace(
            "chat_session_naming",
            group_id=str(chat_session_id),
            metadata=ChatTraceMetadata(
                chat_session_id=str(chat_session_id),
                user_id=str(user_id) if user_id else None,
            ).model_dump(),
        ):
            return generate_chat_session_name(
                chat_history=simple_chat_history,
                llm=llm,
            )
    except Exception as error:
        logger.warning("Failed to generate chat session name: %s", error)
        return fallback_name


@router.put("/rename-chat-session")
def rename_chat_session(
    rename_req: ChatRenameRequest,
    request: Request,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
) -> RenameChatSessionResponse:
    name = rename_req.name
    chat_session_id = rename_req.chat_session_id
    user_id = user.id

    if name:
        with get_session_with_current_tenant() as db_session:
            chat_session = update_chat_session(
                db_session=db_session,
                user_id=user_id,
                chat_session_id=chat_session_id,
                description=name,
            )
        # Echo what was stored: a content-free session drops the title, and
        # reporting the requested one would show a rename that did not happen.
        return RenameChatSessionResponse(new_name=chat_session.description or "")

    # Close the read session before the LLM's multi-second generation window.
    with get_session_with_current_tenant() as db_session:
        chat_session = get_chat_session_by_id(
            chat_session_id=chat_session_id,
            user_id=user_id,
            db_session=db_session,
            eager_load_persona=True,
        )
        # Auto-naming derives a title from the conversation and writes it to the
        # session row. A non-persisting incognito mode keeps no content in
        # Postgres, so it keeps the fallback name and skips the LLM call.
        if not record_mode_persists_content(chat_session.incognito_record_mode):
            return RenameChatSessionResponse(new_name=DEFAULT_CHAT_SESSION_NAME)
        full_history = create_chat_history_chain(
            chat_session_id=chat_session_id,
            db_session=db_session,
        )
        session_override = chat_session.llm_override
    new_name = _generate_or_fallback_chat_session_name(
        chat_history=full_history,
        request=request,
        user=user,
        chat_session_id=chat_session_id,
        persona=chat_session.persona,
        llm_override=session_override,
    )

    with get_session_with_current_tenant() as db_session:
        update_chat_session(
            db_session=db_session,
            user_id=user_id,
            chat_session_id=chat_session_id,
            description=new_name,
        )

    return RenameChatSessionResponse(new_name=new_name)


@router.patch("/chat-session/{session_id}")
def patch_chat_session(
    session_id: UUID,
    chat_session_update_req: ChatSessionUpdateRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    user_id = user.id
    update_chat_session(
        db_session=db_session,
        user_id=user_id,
        chat_session_id=session_id,
        sharing_status=chat_session_update_req.sharing_status,
    )
    return None


def _teardown_incognito_after_delete(
    chat_session_id: UUID, user_id: UUID, db_session: Session
) -> None:
    """The rows are already gone, so a failed teardown is logged rather than
    failing a delete the caller cannot retry. The context TTL is the backstop.

    Uploads are queued here too, so deleting a chat cleans up the same things
    the dedicated teardown endpoint does."""
    try:
        mark_incognito_user_files_deleting(db_session, chat_session_id, user_id)
        db_session.commit()
    except Exception:
        logger.exception("Incognito file cleanup failed for %s", chat_session_id)
    try:
        teardown_incognito_session(chat_session_id)
    except Exception:
        logger.exception("Incognito teardown failed for session %s", chat_session_id)


@router.delete("/delete-all-chat-sessions", tags=PUBLIC_API_TAGS)
def delete_all_chat_sessions(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    incognito_session_ids = get_incognito_session_ids_for_user(user.id, db_session)
    # Blobs first, and nothing is deleted while any remain: their ids live on
    # the rows this is about to drop, so the other order strands them.
    if not all(
        delete_incognito_generated_files(incognito_id, db_session)
        for incognito_id in incognito_session_ids
    ):
        raise NortPoleError(
            NortPoleErrorCode.SERVICE_UNAVAILABLE,
            "Some generated files could not be deleted yet. Try again shortly.",
        )
    try:
        delete_all_chat_sessions_for_user(user=user, db_session=db_session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    for incognito_id in incognito_session_ids:
        _teardown_incognito_after_delete(incognito_id, user.id, db_session)


@router.delete("/delete-chat-session/{session_id}", tags=PUBLIC_API_TAGS)
def delete_chat_session_by_id(
    session_id: UUID,
    hard_delete: bool | None = None,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    user_id = user.id
    try:
        session = get_chat_session_by_id(
            chat_session_id=session_id, user_id=user_id, db_session=db_session
        )
        is_incognito = session.incognito_record_mode is not None
        if is_incognito and not delete_incognito_generated_files(
            session_id, db_session
        ):
            raise NortPoleError(
                NortPoleErrorCode.SERVICE_UNAVAILABLE,
                "Some generated files could not be deleted yet. Try again shortly.",
            )
        # Use the provided hard_delete parameter if specified, otherwise use the default config
        actual_hard_delete = (
            hard_delete if hard_delete is not None else HARD_DELETE_CHATS
        )
        delete_chat_session(
            user_id, session_id, db_session, hard_delete=actual_hard_delete
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if is_incognito:
        _teardown_incognito_after_delete(session_id, user.id, db_session)


class IncognitoAvailabilityResponse(BaseModel):
    available: bool


@router.get("/incognito-availability")
def get_incognito_availability(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> IncognitoAvailabilityResponse:
    """Whether the acting user may start an incognito chat, so the client can
    hide the toggle. The create endpoint enforces the same rule regardless."""
    return IncognitoAvailabilityResponse(
        available=incognito_allowed_for_user(user, db_session)
    )


@router.post("/end-incognito-session/{session_id}", tags=PUBLIC_API_TAGS)
def end_incognito_session(
    session_id: UUID,
    bg_tasks: BackgroundTasks,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    """Drop an incognito session's live context the moment the chat closes.

    The context TTL is only the backstop for when this never arrives, such as
    a hard tab close. Uploads are found by session id, so one still in flight
    when the user leaves, or one attached before any message created the
    session, is queued for deletion just the same.
    """
    if not is_incognito_teardown_target(db_session, session_id, user.id):
        return
    # Durable file marking runs before the Redis teardown: the beacon is
    # one-shot, so a failure after this point still leaves the files queued
    # for deletion rather than stored but hidden.
    deletable_ids = mark_incognito_user_files_deleting(db_session, session_id, user.id)
    db_session.commit()

    # Nothing past the commit may raise. This is a one-shot beacon, so an error
    # reaches nobody who can act on it, and raising would discard the response
    # carrying the in-process drain that a Celery-less deployment relies on.
    enqueue_user_file_deletes(
        deletable_ids, tenant_id=get_current_tenant_id(), bg_tasks=bg_tasks
    )
    for what, step in (
        (
            "delete generated files",
            lambda: delete_incognito_generated_files(session_id, db_session),
        ),
        ("end the context", lambda: teardown_incognito_session(session_id)),
    ):
        try:
            if step() is False:
                logger.warning(
                    "Incognito teardown could not %s for %s", what, session_id
                )
        except Exception:
            logger.exception("Incognito teardown could not %s for %s", what, session_id)


# NOTE: This endpoint is extremely central to the application, any changes to it should be reviewed and approved by an experienced
# team member. It is very important to 1. avoid bloat and 2. that this remains backwards compatible across versions.
@router.post(
    "/send-chat-message",
    response_model=ChatFullResponse,
    tags=PUBLIC_API_TAGS,
    responses={
        200: {
            "description": (
                "If `stream=true`, returns `text/event-stream`.\n"
                "If `stream=false`, returns `application/json` (ChatFullResponse)."
            ),
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "examples": {
                        "stream": {
                            "summary": "Stream of NDJSON AnswerStreamPart's",
                            "value": "string",
                        }
                    },
                },
            },
        }
    },
)
def handle_send_chat_message(
    chat_message_req: SendMessageRequest,
    request: Request,
    user: User = Depends(
        require_permission(Permission.WRITE_CHAT, allow_anonymous=True)
    ),
    _rate_limit_check: None = Depends(check_token_rate_limits),
    _api_key_usage_check: None = Depends(check_api_key_usage),
) -> StreamingResponse | ChatFullResponse:
    """
    This endpoint is used to send a new chat message.

    Args:
        chat_message_req (SendMessageRequest): Details about the new chat message.
            - When stream=True (default): Returns StreamingResponse with SSE
            - When stream=False: Returns ChatFullResponse with complete data
        request (Request): The current HTTP request context.
        user (User): The current user, obtained via dependency injection.
        _ (None): Rate limit check is run if user/group/global rate limits are enabled.

    Returns:
        StreamingResponse | ChatFullResponse: Either streams or returns complete response.
    """
    if chat_message_req.search_evidence:
        token_scopes: list[Permission] | None = getattr(  # ods: ignore[getattr]
            request.state, "token_scopes", None
        )
        if user.is_anonymous or not has_global_permission(user, Permission.READ_SEARCH) or (
            token_scopes is not None and Permission.READ_SEARCH.value not in
            resolve_effective_permissions({permission.value for permission in token_scopes})
        ):
            raise NortPoleError(
                NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
                "You do not have permission to use Search evidence.",
            )

    # Session id only: the session's incognito mode isn't loaded yet, and a
    # verbatim prompt in the debug log would be exactly the durable message
    # log incognito must never leave behind.
    logger.debug(
        "Received new chat message for session %s", chat_message_req.chat_session_id
    )

    tenant_id = get_current_tenant_id()
    mt_cloud_telemetry(
        tenant_id=tenant_id,
        distinct_id=tenant_id if user.is_anonymous else str(user.id),
        event=MilestoneRecordType.RAN_QUERY,
    )

    # Override origin to API when authenticated via API key or PAT
    # to prevent clients from polluting telemetry data
    if get_hashed_api_key_from_request(request) or get_hashed_pat_from_request(request):
        chat_message_req.origin = MessageOrigin.API

    # Multi-model streaming path: 2-3 LLMs in parallel (streaming only)
    is_multi_model = (
        chat_message_req.llm_overrides is not None
        and len(chat_message_req.llm_overrides) > 1
    )
    if is_multi_model and chat_message_req.stream:
        # Narrowed here; is_multi_model already checked llm_overrides is not None
        llm_overrides = chat_message_req.llm_overrides or []

        def multi_model_stream_generator() -> Generator[str, None, None]:
            try:
                for obj in handle_multi_model_stream(
                    new_msg_req=chat_message_req,
                    user=user,
                    llm_overrides=llm_overrides,
                    litellm_additional_headers=get_relevant_headers(
                        request.headers, LITELLM_PASS_THROUGH_HEADERS
                    ),
                    custom_tool_additional_headers=get_relevant_headers(
                        request.headers, CUSTOM_TOOL_PASS_THROUGH_HEADERS
                    ),
                    mcp_headers=chat_message_req.mcp_headers,
                ):
                    yield get_json_line(obj.model_dump())
            except Exception as e:
                logger.exception("Error in multi-model streaming")
                yield json.dumps({"error": str(e)})

        return StreamingResponse(
            multi_model_stream_generator(), media_type="text/event-stream"
        )

    if is_multi_model and not chat_message_req.stream:
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT,
            "Multi-model mode (llm_overrides with >1 entry) requires stream=True.",
        )

    # Non-streaming path: consume all packets and return complete response
    if not chat_message_req.stream:
        if is_usage_limits_enabled():
            with get_session_with_current_tenant() as usage_db_session:
                check_usage_and_raise(
                    db_session=usage_db_session,
                    usage_type=UsageType.NON_STREAMING_API_CALLS,
                    tenant_id=tenant_id,
                    pending_amount=1,
                )
                increment_usage(
                    db_session=usage_db_session,
                    usage_type=UsageType.NON_STREAMING_API_CALLS,
                    amount=1,
                )
                usage_db_session.commit()

        result = run_chat_turn(
            new_msg_req=chat_message_req,
            user=user,
            litellm_additional_headers=get_relevant_headers(
                request.headers, LITELLM_PASS_THROUGH_HEADERS
            ),
            custom_tool_additional_headers=get_relevant_headers(
                request.headers, CUSTOM_TOOL_PASS_THROUGH_HEADERS
            ),
            mcp_headers=chat_message_req.mcp_headers,
            additional_context=chat_message_req.additional_context,
        )
        # CreateChatSessionID is only yielded for newly-created sessions, so for
        # follow-up messages on an existing session the aggregated response would
        # otherwise omit chat_session_id. Backfill it from the request so the
        # field is always present for non-streaming clients.
        if (
            result.chat_session_id is None
            and chat_message_req.chat_session_id is not None
        ):
            result.chat_session_id = chat_message_req.chat_session_id
        return result

    # Streaming path, normal NortPole UI behavior
    def stream_generator() -> Generator[str, None, None]:
        response_future = Future[ChatResponseOutcome]()
        try:
            for obj in handle_stream_message_objects(
                new_msg_req=chat_message_req,
                user=user,
                litellm_additional_headers=get_relevant_headers(
                    request.headers, LITELLM_PASS_THROUGH_HEADERS
                ),
                custom_tool_additional_headers=get_relevant_headers(
                    request.headers, CUSTOM_TOOL_PASS_THROUGH_HEADERS
                ),
                mcp_headers=chat_message_req.mcp_headers,
                additional_context=chat_message_req.additional_context,
                response_future=response_future,
            ):
                yield get_json_line(obj.model_dump())

        except Exception as e:
            logger.exception("Error in chat message streaming")
            yield json.dumps({"error": str(e)})

        finally:
            logger.debug("Stream generator finished")

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


@router.put("/set-message-as-latest")
def set_message_as_latest(
    message_identifier: ChatMessageIdentifier,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    user_id = user.id

    chat_message = get_chat_message(
        chat_message_id=message_identifier.message_id,
        user_id=user_id,
        db_session=db_session,
    )

    set_as_latest_chat_message(
        chat_message=chat_message,
        user_id=user_id,
        db_session=db_session,
    )


@router.put("/set-preferred-response")
def set_preferred_response_endpoint(
    request_body: SetPreferredResponseRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    """Set the preferred assistant response for a multi-model turn."""
    try:
        # Ownership check: get_chat_message raises ValueError if the message
        # doesn't belong to this user, preventing cross-user mutation.
        get_chat_message(
            chat_message_id=request_body.user_message_id,
            user_id=user.id,
            db_session=db_session,
        )
        set_preferred_response(
            db_session=db_session,
            user_message_id=request_body.user_message_id,
            preferred_assistant_message_id=request_body.preferred_response_id,
        )
    except ValueError as e:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, str(e))


@router.post(
    "/create-chat-message-feedback",
    dependencies=get_feedback_rate_limiters(),
)
def create_chat_feedback(
    feedback: ChatFeedbackRequest,
    user: User = Depends(current_chat_accessible_user),
    db_session: Session = Depends(get_session),
) -> None:
    user_id = user.id

    create_chat_message_feedback(
        is_positive=feedback.is_positive,
        feedback_text=feedback.feedback_text,
        predefined_feedback=feedback.predefined_feedback,
        chat_message_id=feedback.chat_message_id,
        user_id=user_id,
        db_session=db_session,
    )


@router.delete(
    "/remove-chat-message-feedback",
    dependencies=get_feedback_rate_limiters(),
)
def remove_chat_feedback(
    chat_message_id: int,
    user: User = Depends(current_chat_accessible_user),
    db_session: Session = Depends(get_session),
) -> None:
    user_id = user.id

    remove_chat_message_feedback(
        chat_message_id=chat_message_id,
        user_id=user_id,
        db_session=db_session,
    )


class MaxSelectedDocumentTokens(BaseModel):
    max_tokens: int


@router.get("/max-selected-document-tokens")
def get_max_document_tokens(
    persona_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MaxSelectedDocumentTokens:
    try:
        persona = get_persona_by_id(
            persona_id=persona_id,
            user=user,
            db_session=db_session,
            is_for_edit=False,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Persona not found")

    return MaxSelectedDocumentTokens(
        max_tokens=_get_available_tokens_for_persona(
            persona=persona,
            user=user,
            db_session=db_session,
        ),
    )


class AvailableContextTokensResponse(BaseModel):
    available_tokens: int


@router.get("/available-context-tokens/{session_id}")
def get_available_context_tokens_for_session(
    session_id: UUID,
    model_configuration_id: int | None = None,
    user: User = Depends(current_chat_accessible_user),
    db_session: Session = Depends(get_session),
) -> AvailableContextTokensResponse:
    """Return available context tokens for a chat session based on its persona.

    ``model_configuration_id`` selects the model the user currently has picked
    for the session — without it the budget reflects the persona/global
    default model, which can differ after a mid-session model switch.
    """

    try:
        chat_session = get_chat_session_by_id(
            chat_session_id=session_id,
            user_id=user.id,
            db_session=db_session,
            is_shared=False,
            include_deleted=False,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Chat session not found")

    if not chat_session.persona:
        raise HTTPException(status_code=400, detail="Chat session has no persona")

    llm_override = (
        LLMOverride(model_configuration_id=model_configuration_id)
        if model_configuration_id is not None
        else None
    )
    available = _get_available_tokens_for_persona(
        persona=chat_session.persona,
        user=user,
        db_session=db_session,
        llm_override=llm_override,
    )

    return AvailableContextTokensResponse(available_tokens=available)


"""Endpoints for chat seeding"""


class SeedChatFromSlackRequest(BaseModel):
    chat_session_id: UUID


class SeedChatFromSlackResponse(BaseModel):
    redirect_url: str


@router.post("/seed-chat-session-from-slack")
def seed_chat_from_slack(
    chat_seed_request: SeedChatFromSlackRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> SeedChatFromSlackResponse:
    slack_chat_session_id = chat_seed_request.chat_session_id
    new_chat_session = duplicate_chat_session_for_user_from_slack(
        db_session=db_session,
        user=user,
        chat_session_id=slack_chat_session_id,
    )

    add_chats_to_session_from_slack_thread(
        db_session=db_session,
        slack_chat_session_id=slack_chat_session_id,
        new_chat_session_id=new_chat_session.id,
    )

    return SeedChatFromSlackResponse(
        redirect_url=f"{WEB_DOMAIN}/chat?chatId={new_chat_session.id}"
    )


@router.get("/file/{file_id:path}", tags=PUBLIC_API_TAGS)
def fetch_chat_file(
    file_id: str,
    request: Request,
    parsed: bool = Query(False),
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
    fresh: bool = False,
) -> Response:
    # For user files, we need to get the file id from the user file id
    file_id_from_user_file = get_file_id_by_user_file_id(file_id, db_session)
    if file_id_from_user_file:
        file_id = file_id_from_user_file

    if not user_can_access_chat_file(file_id, user, db_session):
        # Return 404 (rather than 403) so callers cannot probe for file
        # existence across ownership boundaries.
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "File not found")

    file_store = get_default_file_store()
    file_record = file_store.read_file_record(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    # `parsed` only changes behavior for spreadsheet files (xlsx is a binary zip
    # the frontend cannot render); everything else is served raw as usual.
    parse_spreadsheet = parsed and is_spreadsheet_mime_type(file_record.file_type)

    media_type, security_headers = resolve_inline_disposition(
        file_record.file_type,
        filename=ensure_filename_extension(
            file_record.display_name or file_id, file_record.file_type
        ),
        attachment_types=ATTACHMENT_SAFE_MIME_TYPES,
        # A parsed spreadsheet is served as a JSON preview, not as the stored bytes.
        fallback_disposition=None if parse_spreadsheet else "attachment",
    )

    # Search links opt out of caching so reopening the file checks current access.
    etag_variant: str = "-parsed" if parse_spreadsheet else ""
    etag: str = f'"{file_id}{etag_variant}-{RESPONSE_POLICY_VERSION}"'
    cache_headers: dict[str, str] = {
        "Cache-Control": "private, no-store" if fresh else "private, max-age=31536000, immutable",
        "ETag": etag,
        "Vary": "Cookie",
        **security_headers,
    }

    if not fresh and request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)

    if parse_spreadsheet:
        # Use a tempfile since openpyxl needs a seekable file and the workbook
        # may be large.
        with file_store.read_file(file_id, mode="b", use_tempfile=True) as xlsx_io:
            preview = parse_spreadsheet_for_preview(
                xlsx_io, file_record.display_name or ""
            )
        return JSONResponse(content=preview.model_dump(), headers=cache_headers)

    file_io = file_store.read_file(file_id, mode="b")
    return StreamingResponse(file_io, media_type=media_type, headers=cache_headers)


@router.get("/search", tags=PUBLIC_API_TAGS)
def search_chats(
    query: str | None = Query(None),
    page: int = Query(1),
    page_size: int = Query(10),
    user: User = Depends(require_permission(Permission.READ_CHAT)),
    db_session: Session = Depends(get_session),
) -> ChatSearchResponse:
    """
    Search for chat sessions based on the provided query.
    If no query is provided, returns recent chat sessions.
    """

    # Use the enhanced database function for chat search
    chat_sessions, has_more = search_chat_sessions(
        user_id=user.id,
        db_session=db_session,
        query=query,
        page=page,
        page_size=page_size,
        include_deleted=False,
    )

    # Group chat sessions by time period
    today = datetime.datetime.now().date()
    yesterday = today - timedelta(days=1)
    this_week = today - timedelta(days=7)
    this_month = today - timedelta(days=30)

    today_chats: list[ChatSessionSummary] = []
    yesterday_chats: list[ChatSessionSummary] = []
    this_week_chats: list[ChatSessionSummary] = []
    this_month_chats: list[ChatSessionSummary] = []
    older_chats: list[ChatSessionSummary] = []

    for session in chat_sessions:
        session_date = session.time_created.date()

        chat_summary = ChatSessionSummary(
            id=session.id,
            name=session.description,
            persona_id=session.persona_id,
            time_created=session.time_created,
            shared_status=session.shared_status,
            current_alternate_model=session.current_alternate_model,
            current_temperature_override=session.temperature_override,
            current_reasoning_effort_override=session.reasoning_effort_override,
        )

        if session_date == today:
            today_chats.append(chat_summary)
        elif session_date == yesterday:
            yesterday_chats.append(chat_summary)
        elif session_date > this_week:
            this_week_chats.append(chat_summary)
        elif session_date > this_month:
            this_month_chats.append(chat_summary)
        else:
            older_chats.append(chat_summary)

    # Create groups
    groups = []
    if today_chats:
        groups.append(ChatSessionGroup(title="Today", chats=today_chats))
    if yesterday_chats:
        groups.append(ChatSessionGroup(title="Yesterday", chats=yesterday_chats))
    if this_week_chats:
        groups.append(ChatSessionGroup(title="This Week", chats=this_week_chats))
    if this_month_chats:
        groups.append(ChatSessionGroup(title="This Month", chats=this_month_chats))
    if older_chats:
        groups.append(ChatSessionGroup(title="Older", chats=older_chats))

    return ChatSearchResponse(
        groups=groups,
        has_more=has_more,
        next_page=page + 1 if has_more else None,
    )


# ~32 KiB decompressed per chunk → ~1 MiB peak per read; a full-buffer replay
# would otherwise materialize up to the whole decompressed buffer at once.
_RESUME_MAX_CHUNKS_PER_READ = 32


@router.get("/chat-session/{session_id}/status")
def get_chat_session_processing_status(
    session_id: UUID,
    user: User = Depends(
        require_permission(Permission.READ_CHAT, allow_anonymous=True)
    ),
) -> ChatSessionProcessingStatus:
    with get_session_with_current_tenant() as db_session:
        try:
            get_chat_session_by_id(
                chat_session_id=session_id,
                user_id=user.id,
                db_session=db_session,
            )
        except ValueError as error:
            raise NortPoleError(NortPoleErrorCode.SESSION_NOT_FOUND) from error
    return ChatSessionProcessingStatus(
        is_processing=is_chat_session_processing(session_id, get_cache_backend())
    )


@router.get("/chat-session/{session_id}/resume-stream")
def resume_chat_stream(
    session_id: UUID,
    cursor: int = Query(0, ge=0),
    expected_stream_id: int | None = Query(None, alias="stream_id", gt=0),
    user: User = Depends(
        require_permission(Permission.READ_CHAT, allow_anonymous=True)
    ),
) -> StreamingResponse:
    """Replay buffered output from ``cursor`` and tail it while its worker is live.
    Serves any pod: the buffer lives in the
    shared cache. 404 when the session has no resumable run — the client
    falls back to refetching the session."""
    # Short-lived session: a Depends(get_session) would stay checked out (idle
    # in transaction) for the lifetime of the SSE response.
    with get_session_with_current_tenant() as db_session:
        try:
            get_chat_session_by_id(
                chat_session_id=session_id,
                user_id=user.id,
                db_session=db_session,
            )
        except ValueError:
            raise NortPoleError(NortPoleErrorCode.SESSION_NOT_FOUND)

    cache = get_cache_backend()
    stream_id = get_processing_stream_id(session_id, cache)
    if (
        stream_id is None
        or (expected_stream_id is not None and expected_stream_id != stream_id)
        or not has_stream_buffer(cache, session_id, stream_id)
    ):
        raise NortPoleError(
            NortPoleErrorCode.NOT_FOUND, "No resumable stream for this chat session"
        )

    def stream_buffered_run() -> Generator[str, None, None]:
        chunk_cursor = cursor
        replay_through: int | None = None
        writer_stopped = False
        last_emit = time.monotonic()
        while True:
            read = read_stream_chunks(
                cache,
                session_id,
                stream_id,
                chunk_cursor,
                max_chunks=(
                    min(_RESUME_MAX_CHUNKS_PER_READ, replay_through - chunk_cursor)
                    if replay_through is not None and chunk_cursor < replay_through
                    else _RESUME_MAX_CHUNKS_PER_READ
                ),
            )
            # Buffer expired/evicted or sequence broken: end the stream — the
            # client refetches the session and renders the persisted message.
            if read is None or read.gap or chunk_cursor > read.chunk_count:
                return
            initial_read = replay_through is None
            if replay_through is None:
                # Freeze the restore boundary so new writes cannot prolong replay.
                replay_through = read.chunk_count
            if read.blocks or initial_read:
                yield "".join(read.blocks)
                chunk_cursor = read.next_cursor
                yield get_json_line(
                    StreamCursor(
                        stream_id=stream_id,
                        next_cursor=chunk_cursor,
                        replay_complete=chunk_cursor >= replay_through,
                    ).model_dump()
                )
            if read.blocks:
                last_emit = time.monotonic()
                # Drain the backlog before sleeping; done is only trusted once
                # a read comes back empty (a capped read can precede the tail).
                continue
            if read.done or writer_stopped:
                return
            # Drain once more after ownership ends to catch the writer's last flush.
            if not is_chat_session_processing(session_id, cache):
                writer_stopped = True
                continue
            now = time.monotonic()
            if now - last_emit >= CHAT_HEARTBEAT_INTERVAL_S:
                yield get_json_line(heartbeat_packet().model_dump())
                last_emit = now
            time.sleep(CHAT_RESUME_POLL_INTERVAL_S)

    return StreamingResponse(stream_buffered_run(), media_type="text/event-stream")


@router.post("/stop-chat-session/{chat_session_id}", tags=PUBLIC_API_TAGS)
def stop_chat_session(
    chat_session_id: UUID,
    stream_id: int | None = Query(default=None, gt=0),
    user: User = Depends(require_permission(Permission.WRITE_CHAT)),
    db_session: Session = Depends(get_session),
) -> StopChatResponse:
    """Stop the requested execution without affecting a later request."""
    try:
        get_chat_session_by_id(
            chat_session_id=chat_session_id,
            user_id=user.id,
            db_session=db_session,
        )
    except ValueError as error:
        raise NortPoleError(
            NortPoleErrorCode.SESSION_NOT_FOUND, "Chat session not found"
        ) from error

    cache = get_cache_backend()
    target_stream_id = stream_id or get_processing_stream_id(chat_session_id, cache)
    if target_stream_id is not None:
        request_stop(chat_session_id, cache, stream_id=target_stream_id)
    return StopChatResponse(message="Chat session stopped")
