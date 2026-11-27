"""Validate and run a saved, read-only Expense Review as its owner."""

from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID, uuid4

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from nortpole.agents.models import RunStatus
from nortpole.auth.permissions import has_global_permission
from nortpole.chat.process_message import run_chat_turn
from nortpole.chat.selected_sources import MAX_INLINE_CSV_BYTES
from nortpole.configs.constants import DEFAULT_PERSONA_ID, FileOrigin
from nortpole.context.search.models import BaseFilters
from nortpole.db.chat import create_chat_session
from nortpole.db.document_set import get_document_set_by_id_for_user
from nortpole.db.enums import Permission, UserFileStatus
from nortpole.db.models import ChatMessage, User, UserFile
from nortpole.db.user_file import get_user_file_by_id
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.file_store.models import ChatFileType, FileDescriptor
from nortpole.file_store.utils import get_default_file_store
from nortpole.external_apps.token_refresh import ensure_fresh_credentials
from nortpole.server.features.build.utils import is_craft_enabled_for_user
from nortpole.server.query_and_chat.models import ChatSessionCreationRequest, SendMessageRequest
from nortpole.server.query_and_chat.token_limit import check_token_rate_limits
from nortpole.server.settings.store import load_settings
from nortpole.work.workflow_schedules.drive_csv import (
    NoNewDriveCsv, download_csv, drive_headers, newest_csv, validate_drive_source,
)
from nortpole.work.workflow_schedules.models import DriveRunSource, ExpenseReviewInputs, NortPoleWorkflowRun
from shared_configs.contextvars import get_current_tenant_id

RECEIPT_REVIEW_REQUEST = "Review these expenses for receipt compliance."


def _resolve_library(db: Session, owner: User, inputs: ExpenseReviewInputs) -> str:
    if not (
        has_global_permission(owner, Permission.WRITE_CHAT)
        and has_global_permission(owner, Permission.READ_SEARCH)
    ):
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "Expense Review requires Chat and Knowledge access.",
        )
    library = get_document_set_by_id_for_user(db, inputs.library_id, owner, get_editable=False)
    if library is None:
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "The selected Knowledge library is unavailable.",
        )
    return library.name


def validate_inputs(db: Session, owner: User, inputs: ExpenseReviewInputs) -> None:
    if inputs.drive_source is None:
        resolve_inputs(db, owner, inputs)
    else:
        _resolve_library(db, owner, inputs)
        _require_drive_integration_access(owner)
        validate_drive_source(db, owner.id, inputs.drive_source)


def _require_drive_integration_access(owner: User) -> None:
    if not is_craft_enabled_for_user(owner):
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "The Google Drive app requires access to personal integrations.",
        )


def resolve_inputs(
    db: Session, owner: User, inputs: ExpenseReviewInputs
) -> tuple[str, FileDescriptor]:
    library = _resolve_library(db, owner, inputs)
    assert inputs.csv_file_id is not None
    file = get_user_file_by_id(inputs.csv_file_id, db)
    if file is None or file.user_id != owner.id or file.incognito:
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "The selected CSV is unavailable.",
        )
    if not file.name.lower().endswith(".csv") or file.status not in {
        UserFileStatus.COMPLETED, UserFileStatus.SKIPPED,
    }:
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT,
            "Choose an uploaded CSV that has finished processing.",
        )
    try:
        size = get_default_file_store().get_file_size(file.file_id)
    except FileNotFoundError as exc:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "The selected CSV is unavailable.") from exc
    if size is None or size > MAX_INLINE_CSV_BYTES:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose one CSV of up to 12 KB.")
    return library, FileDescriptor(
        id=file.file_id, user_file_id=str(file.id), name=file.name, type=ChatFileType.TABULAR,
    )


def run_expense_review(
    db: Session, owner: User, inputs: ExpenseReviewInputs, *, run: NortPoleWorkflowRun | None = None,
) -> tuple[str, UUID]:
    library, descriptor = resolve_inputs(db, owner, inputs)
    return _run_review(db, owner, inputs, library, descriptor, run=run)


def run_drive_expense_review(
    db: Session, owner: User, inputs: ExpenseReviewInputs, schedule_id: UUID,
    *, run: NortPoleWorkflowRun | None = None,
) -> tuple[str, UUID, DriveRunSource]:
    source = inputs.drive_source
    assert source is not None
    library = _resolve_library(db, owner, inputs)
    _require_drive_integration_access(owner)
    ensure_fresh_credentials(get_current_tenant_id(), source.app_id, owner.id)
    headers = drive_headers(db, owner.id, source.app_id)
    db.commit()
    latest = newest_csv(source, headers)
    revision = DriveRunSource(
        app_id=source.app_id, folder_id=source.folder_id, file_id=latest.id,
        version=latest.version, file_name=latest.name,
        library_name=library, policy_title="",
    )
    previous = db.scalar(
        select(NortPoleWorkflowRun.outcome).where(
            NortPoleWorkflowRun.schedule_id == schedule_id,
            NortPoleWorkflowRun.outcome.in_(("review_complete", "needs_review", "running", "interrupted")),
            cast(NortPoleWorkflowRun.drive_source, JSONB).contains(revision.model_dump(
                include={"app_id", "folder_id", "file_id", "version"},
            )),
        ).limit(1)
    )
    if previous is not None:
        if previous in {"running", "interrupted"}:
            raise NoNewDriveCsv("A review of the latest Google Drive CSV is unfinished. Check its outcome in Runs.")
        raise NoNewDriveCsv("The latest matching Google Drive CSV has already been reviewed.")
    db.commit()
    content = download_csv(latest, headers)
    # Keep a private, unindexed snapshot so the run can be audited after Drive changes.
    store = get_default_file_store()
    storage_id = store.save_file(
        BytesIO(content), latest.name, FileOrigin.USER_FILE, "text/csv",
    )
    file = UserFile(
        id=uuid4(), user_id=owner.id, file_id=storage_id, name=latest.name,
        status=UserFileStatus.SKIPPED, file_type="text/csv", content_type="text/csv",
        link_url=f"https://drive.google.com/open?id={latest.id}",
        last_accessed_at=datetime.now(timezone.utc),
    )
    try:
        db.add(file)
        db.commit()
    except Exception:
        db.rollback()
        store.delete_file(storage_id)
        raise
    descriptor = FileDescriptor(
        id=storage_id, user_file_id=str(file.id), name=latest.name, type=ChatFileType.TABULAR,
    )
    outcome, chat_id = _run_review(db, owner, inputs, library, descriptor, revision=revision, run=run)
    return outcome, chat_id, revision


def _run_review(
    db: Session, owner: User, inputs: ExpenseReviewInputs, library: str, descriptor: FileDescriptor,
    *, revision: DriveRunSource | None = None, run: NortPoleWorkflowRun | None = None,
) -> tuple[str, UUID]:
    if load_settings().disable_default_assistant:
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT,
            "Scheduled Expense Review requires the default Chat assistant.",
        )
    check_token_rate_limits(owner)
    chat_id = None
    if run is not None:
        chat = create_chat_session(db, "Scheduled Expense Review", owner.id, DEFAULT_PERSONA_ID, commit=False)
        db.flush()
        chat_id = run.chat_session_id = chat.id
        run.drive_source = revision.model_copy() if revision is not None else None
    db.commit()

    def link_response(response_id: int) -> None:
        if run is not None:
            run.chat_result_id = response_id
            db.commit()

    result = run_chat_turn(SendMessageRequest(
        message=RECEIPT_REVIEW_REQUEST,
        model_selection="auto",
        receipt_review_policy_title=inputs.policy_title.strip(),
        ground_selected_knowledge=True,
        internal_search_filters=BaseFilters(document_set=[library]),
        file_descriptors=[descriptor],
        chat_session_id=chat_id,
        chat_session_info=None if chat_id else ChatSessionCreationRequest(description="Scheduled Expense Review"),
        stream=False,
    ), owner, on_response_reserved=link_response if run is not None else None)
    response = db.get(ChatMessage, result.message_id)
    if (
        result.error_msg
        or response is None
        or response.response_status != RunStatus.COMPLETE
        or response.receipt_review_needs_review is None
    ):
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT, result.error_msg or "The expense review did not finish."
        )
    if revision is not None:
        cited = {citation.document_id for citation in result.citation_info}
        revision.policy_title = next(
            (doc.semantic_identifier for doc in result.top_documents if doc.document_id in cited),
            "",
        )
    return (
        "needs_review" if response.receipt_review_needs_review else "review_complete",
        response.chat_session_id,
    )
