from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from nortpole.agents.models import RunStatus
from nortpole.chat.document_review import DocumentReview, ReviewContext, VerifiedFinding
from nortpole.configs.constants import MessageType, NotificationType
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import ChatMessage, ChatSession, Notification, User
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.query_and_chat.chat_backend import list_workflow_runs
from nortpole.work.document_reviews import DecisionRequest, get_review, record_decision, revision_source
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")


def test_decisions_preserve_history_and_clear_or_reopen_the_owners_inbox() -> None:
    with get_session_with_current_tenant() as db:
        owner = User(email=f"{uuid4()}@example.invalid", hashed_password="fixture")
        other = User(email=f"{uuid4()}@example.invalid", hashed_password="fixture")
        db.add_all([owner, other])
        db.flush()
        ids = [owner.id, other.id]

        def notification():
            return db.scalar(select(Notification).where(
                Notification.user_id == owner.id,
                Notification.notif_type == NotificationType.DOCUMENT_REVIEW_NEEDS_REVIEW,
            ))

        try:
            chat = ChatSession(user_id=owner.id, deleted=False)
            db.add(chat)
            db.flush()
            document_review = DocumentReview(
                findings=[VerifiedFinding(status="conflict", explanation="Approval roles differ.")],
                context=ReviewContext(library_id=12, library_name="Travel", pack_id="travel-pack", pack_version="1.0.0"),
            )
            message = ChatMessage(
                chat_session_id=chat.id, message_type=MessageType.ASSISTANT,
                message="Result", token_count=1, response_status=RunStatus.COMPLETE,
                document_review_needs_review=True, document_review_report=document_review.model_dump(mode="json"),
            )
            db.add(message)
            db.commit()
            original = get_review(message.id, owner, db)
            assert original.open_findings == 1
            assert original.findings[0].decisions == []
            assert not original.can_review_revision
            with pytest.raises(NortPoleError, match="Request a revision"):
                revision_source(db, owner, message.id, chat_session_id=chat.id)
            assert list_workflow_runs(user=owner, db_session=db).runs[0].status == "needs_review"

            revision = DecisionRequest(request_id=uuid4(), expected_latest_id=None, action="revision_requested")
            with pytest.raises(NortPoleError, match="Document review is unavailable"):
                record_decision(message.id, 1, revision, other, db)
            first = record_decision(message.id, 1, revision, owner, db)
            assert first.open_findings == 1
            assert first.can_review_revision
            context, previous = revision_source(db, owner, message.id, chat_session_id=chat.id)
            assert context == document_review.context
            assert previous == [(1, document_review.findings[0])]
            with pytest.raises(NortPoleError, match="Document review is unavailable"):
                revision_source(db, owner, message.id, chat_session_id=uuid4())
            assert record_decision(message.id, 1, revision, owner, db) == first

            stale = DecisionRequest(request_id=uuid4(), expected_latest_id=None, action="resolved")
            with pytest.raises(NortPoleError, match="finding changed"):
                record_decision(message.id, 1, stale, owner, db)

            accepted = record_decision(message.id, 1, DecisionRequest(
                request_id=uuid4(), expected_latest_id=first.findings[0].decisions[0].id,
                action="exception_accepted", reason="The approved pilot uses a separate process.",
            ), owner, db)
            assert accepted.open_findings == 0
            history = accepted.findings[0].decisions
            assert [entry.action for entry in history] == ["exception_accepted", "revision_requested"]
            assert history[0].reason == "The approved pilot uses a separate process."
            assert all(entry.actor_id == owner.id for entry in history)
            assert list_workflow_runs(user=owner, db_session=db).runs[0].status == "complete"

            # Reopen the finding after the exception has been reconsidered.
            reopened = record_decision(message.id, 1, DecisionRequest(
                request_id=uuid4(), expected_latest_id=history[0].id, action="revision_requested",
            ), owner, db)
            assert reopened.open_findings == 1
            assert notification() is not None and not notification().dismissed

            closed = record_decision(message.id, 1, DecisionRequest(
                request_id=uuid4(), expected_latest_id=reopened.findings[0].decisions[0].id, action="resolved",
            ), owner, db)
            assert closed.open_findings == 0
            assert notification().dismissed
            assert [entry.action for entry in closed.findings[0].decisions] == [
                "resolved", "revision_requested", "exception_accepted", "revision_requested",
            ]

            legacy = ChatMessage(
                chat_session_id=chat.id, message_type=MessageType.ASSISTANT,
                message="Legacy report", token_count=1, response_status=RunStatus.COMPLETE,
                document_review_needs_review=True,
            )
            db.add(legacy)
            db.commit()
            assert get_review(legacy.id, owner, db).open_findings is None
            with pytest.raises(NortPoleError, match="Review finding is unavailable"):
                record_decision(legacy.id, 1, revision, owner, db)

            chat.deleted = True
            db.commit()
            with pytest.raises(NortPoleError, match="Document review is unavailable"):
                get_review(message.id, owner, db)
        finally:
            db.rollback()
            db.execute(delete(User).where(User.id.in_(ids)))
            db.commit()


def test_exception_requires_a_reason() -> None:
    with pytest.raises(ValidationError, match="Give a reason"):
        DecisionRequest(request_id=uuid4(), expected_latest_id=None, action="exception_accepted", reason="   ")
