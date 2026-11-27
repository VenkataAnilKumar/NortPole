"""Owner-only decisions and evidence for saved Document Reviews."""

from collections import defaultdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session, aliased

from nortpole.agents.models import RunStatus
from nortpole.auth.permissions import require_permission
from nortpole.chat.document_review import DOCUMENT_EXTENSIONS, DocumentReview, ReviewContext, RevisionComparison, VerifiedFinding
from nortpole.configs.constants import MessageType, NotificationType
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission, UserFileStatus
from nortpole.db.document_set import get_document_set_by_id_for_user
from nortpole.db.models import ChatMessage, ChatSession, DocumentReviewDecision, Notification, SearchDoc, User
from nortpole.db.notification import create_notification
from nortpole.db.user_file import get_user_file_by_id
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError

router = APIRouter(prefix="/document-reviews")
DecisionAction = Literal["revision_requested", "exception_accepted", "resolved"]


class DecisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    request_id: UUID
    expected_latest_id: int | None = Field(ge=1)
    action: DecisionAction
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def check_reason(self) -> "DecisionRequest":
        if "\x00" in self.reason:
            raise ValueError("The reason contains an invalid character.")
        if self.action == "exception_accepted" and not self.reason:
            raise ValueError("Give a reason for accepting the exception.")
        return self


class DecisionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: DecisionAction
    reason: str
    created_at: datetime
    actor_id: UUID | None


class ReviewCitation(BaseModel):
    number: int
    title: str
    link: str | None


class FindingView(BaseModel):
    number: int
    status: Literal["aligned", "conflict", "needs_review"]
    explanation: str
    document_quote: str
    policy_quote: str
    citation: ReviewCitation | None
    decisions: list[DecisionView]
    is_open: bool


class ReviewView(BaseModel):
    message_id: int
    chat_session_id: UUID
    file_name: str | None
    created_at: datetime
    pack_name: str | None
    open_findings: int | None
    findings: list[FindingView]
    context: ReviewContext | None = None
    revision: RevisionComparison | None = None
    revised_reviews: list[int] = Field(default_factory=list)
    can_review_revision: bool = False


def _is_open(finding: VerifiedFinding, action: str | None) -> bool:
    return action == "revision_requested" if action is not None else finding.status != "aligned"


def open_finding_counts(db: Session, reports: dict[int, dict]) -> dict[int, int]:
    if not reports:
        return {}
    latest = defaultdict(dict)
    for message_id, number, action in db.execute(
        select(DocumentReviewDecision.message_id, DocumentReviewDecision.finding_number, DocumentReviewDecision.action)
        .where(DocumentReviewDecision.message_id.in_(reports))
        .distinct(DocumentReviewDecision.message_id, DocumentReviewDecision.finding_number)
        .order_by(DocumentReviewDecision.message_id, DocumentReviewDecision.finding_number, DocumentReviewDecision.id.desc())
    ):
        latest[message_id][number] = action
    return {
        message_id: sum(
            _is_open(finding, latest[message_id].get(number))
            for number, finding in enumerate(DocumentReview.model_validate(report).numbered_findings(), start=1)
        )
        for message_id, report in reports.items()
    }


def _owned_review(db: Session, user: User, message_id: int, *, lock: bool = False) -> ChatMessage:
    stmt = (
        select(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
        .where(
            ChatMessage.id == message_id,
            ChatMessage.message_type == MessageType.ASSISTANT,
            ChatMessage.response_status == RunStatus.COMPLETE,
            ChatMessage.document_review_needs_review.is_not(None),
            ChatSession.user_id == user.id,
            ChatSession.deleted.is_(False),
            ChatSession.incognito_record_mode.is_(None),
        )
    )
    # Serialize decisions and soft deletion on the same session row.
    if lock:
        stmt = stmt.with_for_update(of=ChatSession)
    message = db.scalar(stmt)
    if message is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Document review is unavailable.")
    return message


def _revision_reports(message: ChatMessage):
    return select(ChatMessage.id).where(
        ChatMessage.chat_session_id == message.chat_session_id,
        ChatMessage.response_status == RunStatus.COMPLETE,
        ChatMessage.document_review_report["revision"]["previous_id"].astext == str(message.id),
    )


def revision_source(
    db: Session, user: User, message_id: int, *, chat_session_id: UUID,
) -> tuple[ReviewContext, list[tuple[int, VerifiedFinding]]]:
    message = _owned_review(db, user, message_id)
    if message.chat_session_id != chat_session_id:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Document review is unavailable.")
    report = DocumentReview.model_validate(message.document_review_report or {})
    if report.context is None:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The original review does not have saved source settings. Start a new Document Review.")
    latest = dict(db.execute(
        select(DocumentReviewDecision.finding_number, DocumentReviewDecision.action)
        .where(DocumentReviewDecision.message_id == message_id)
        .distinct(DocumentReviewDecision.finding_number)
        .order_by(DocumentReviewDecision.finding_number, DocumentReviewDecision.id.desc())
    ).tuples().all())
    if "revision_requested" not in latest.values():
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Request a revision on a finding before reviewing a new version.")
    return report.context, [
        (number, finding)
        for number, finding in enumerate(report.numbered_findings(), start=1)
        if _is_open(finding, latest.get(number))
    ]


def _view(db: Session, message: ChatMessage) -> ReviewView:
    files = message.parent_message.files if message.parent_message else None
    view = ReviewView(
        message_id=message.id, chat_session_id=message.chat_session_id,
        file_name=files[0].get("name") if files else None,
        created_at=message.time_sent, pack_name=None, open_findings=None, findings=[],
    )
    if message.document_review_report is None:
        return view

    report = DocumentReview.model_validate(message.document_review_report)
    citations = message.citations or {}
    documents = {
        doc.id: doc
        for doc in db.scalars(select(SearchDoc).where(SearchDoc.id.in_(citations.values())))
    }
    evidence: dict[str, ReviewCitation] = {}
    for number, document_id in citations.items():
        doc = documents.get(document_id)
        if doc is not None:
            evidence[doc.document_id] = ReviewCitation(number=int(number), title=doc.semantic_id, link=doc.link)

    decisions: dict[int, list[DecisionView]] = defaultdict(list)
    for decision in db.scalars(
        select(DocumentReviewDecision).where(DocumentReviewDecision.message_id == message.id)
        .order_by(DocumentReviewDecision.id.desc())
    ):
        decisions[decision.finding_number].append(DecisionView.model_validate(decision))

    findings = [
        FindingView(
            number=number, status=finding.status, explanation=finding.explanation,
            document_quote=finding.document_quote, policy_quote=finding.policy_quote,
            citation=evidence.get(finding.source_id) if finding.source_id else None,
            decisions=decisions[number],
            is_open=_is_open(finding, decisions[number][0].action if decisions[number] else None),
        )
        for number, finding in enumerate(report.numbered_findings(), start=1)
    ]
    view.pack_name = report.pack_name
    view.context = report.context
    view.revision = report.revision
    view.revised_reviews = list(db.scalars(_revision_reports(message).order_by(ChatMessage.id.desc())))
    view.can_review_revision = report.context is not None and any(
        finding.decisions and finding.decisions[0].action == "revision_requested"
        for finding in findings
    )
    view.open_findings = sum(finding.is_open for finding in findings)
    view.findings = findings
    return view


@router.get("/{message_id}")
def get_review(
    message_id: Annotated[int, Path(ge=1)],
    user: User = Depends(require_permission(Permission.READ_CHAT)),
    db: Session = Depends(get_session),
) -> ReviewView:
    return _view(db, _owned_review(db, user, message_id))


class RevisionRequest(BaseModel):
    file_id: UUID


class RevisionResult(BaseModel):
    message_id: int


@router.post("/{message_id}/revisions")
def review_revision(
    message_id: Annotated[int, Path(ge=1)],
    body: RevisionRequest,
    user: User = Depends(require_permission(Permission.WRITE_CHAT)),
    db: Session = Depends(get_session),
) -> RevisionResult:
    from nortpole.chat.process_message import run_chat_turn
    from nortpole.context.search.models import BaseFilters
    from nortpole.file_store.models import FileDescriptor
    from nortpole.server.query_and_chat.chat_utils import mime_type_to_chat_file_type
    from nortpole.server.query_and_chat.models import SendMessageRequest
    from nortpole.server.query_and_chat.token_limit import check_token_rate_limits

    message = _owned_review(db, user, message_id)
    parent = aliased(ChatMessage)
    already_reviewed = db.scalar(
        _revision_reports(message)
        .join(parent, ChatMessage.parent_message_id == parent.id)
        .where(parent.files.contains([{"user_file_id": str(body.file_id)}]))
        .order_by(ChatMessage.id.desc()).limit(1)
    )
    if already_reviewed is not None:
        return RevisionResult(message_id=already_reviewed)
    context, _ = revision_source(db, user, message.id, chat_session_id=message.chat_session_id)
    library = get_document_set_by_id_for_user(db, context.library_id, user, get_editable=False)
    if library is None:
        raise NortPoleError(NortPoleErrorCode.INSUFFICIENT_PERMISSIONS, "The original Knowledge library is unavailable.")
    file = get_user_file_by_id(body.file_id, db)
    if file is None or file.user_id != user.id or file.incognito:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "The revised attachment is unavailable.")
    original_files = message.parent_message.files if message.parent_message else None
    if original_files and original_files[0].get("id") == file.file_id:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Upload the revised document.")
    if not file.name.lower().endswith(DOCUMENT_EXTENSIONS) or file.status not in {
        UserFileStatus.COMPLETED, UserFileStatus.SKIPPED,
    }:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose a supported document that has finished processing.")
    original_request = message.parent_message.message if message.parent_message else "Review the attached document against the selected Knowledge library."
    request = SendMessageRequest(
        message=original_request, chat_session_id=message.chat_session_id, parent_message_id=message.id,
        file_descriptors=[FileDescriptor(
            id=file.file_id, user_file_id=str(file.id), name=file.name,
            type=mime_type_to_chat_file_type(file.file_type),
        )],
        document_review=True, document_review_previous_id=message.id,
        ground_selected_knowledge=True, internal_search_filters=BaseFilters(document_set=[library.name]),
        model_selection="auto", stream=False,
    )
    check_token_rate_limits(user)
    db.commit()
    result = run_chat_turn(request, user)
    if result.error_msg:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, result.error_msg)
    revised = _owned_review(db, user, result.message_id)
    return RevisionResult(message_id=revised.id)


def _update_review_notification(db: Session, user: User, message: ChatMessage, *, reopen: bool) -> None:
    existing = (
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.notif_type == NotificationType.DOCUMENT_REVIEW_NEEDS_REVIEW,
            Notification.additional_data["message_id"].astext == str(message.id),
        )
        .values(dismissed=not reopen)
        .returning(Notification.id)
    )
    updated = list(db.scalars(existing))
    if reopen and not updated:
        create_notification(
            user_id=user.id, db_session=db, notif_type=NotificationType.DOCUMENT_REVIEW_NEEDS_REVIEW,
            title="A document review needs your attention",
            description="Open the cited report to review the findings.",
            additional_data={
                "chat_session_id": str(message.chat_session_id), "message_id": message.id,
                "link": f"/app/workflows/runs?review={message.id}",
            },
            autocommit=False, refresh_existing=False,
        )


@router.post("/{message_id}/findings/{number}/decisions")
def record_decision(
    message_id: Annotated[int, Path(ge=1)],
    number: Annotated[int, Path(ge=1)],
    body: DecisionRequest,
    user: User = Depends(require_permission(Permission.WRITE_CHAT)),
    db: Session = Depends(get_session),
) -> ReviewView:
    message = _owned_review(db, user, message_id, lock=True)
    current = _view(db, message)
    if number > len(current.findings):
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Review finding is unavailable.")
    finding = current.findings[number - 1]
    prior_request = db.scalar(
        select(DocumentReviewDecision).where(
            DocumentReviewDecision.message_id == message_id,
            DocumentReviewDecision.request_id == body.request_id,
        )
    )
    if prior_request is not None:
        if (prior_request.finding_number, prior_request.action, prior_request.reason) == (number, body.action, body.reason):
            return current
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This request already recorded a different decision.")
    latest = finding.decisions[0].id if finding.decisions else None
    if latest != body.expected_latest_id:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This finding changed. Review its latest decision and try again.")

    db.add(DocumentReviewDecision(
        message_id=message_id, finding_number=number, actor_id=user.id,
        request_id=body.request_id, action=body.action, reason=body.reason,
    ))
    assert current.open_findings is not None
    next_open = current.open_findings - int(finding.is_open) + int(body.action == "revision_requested")
    if bool(current.open_findings) != bool(next_open):
        _update_review_notification(db, user, message, reopen=bool(next_open))
    db.commit()
    return _view(db, message)
