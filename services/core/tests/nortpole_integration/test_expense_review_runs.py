from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from nortpole.agents.models import RunStatus
from nortpole.configs.constants import MessageType
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import IncognitoRecordMode
from nortpole.db.models import ChatMessage, ChatSession, User
from nortpole.server.query_and_chat.chat_backend import list_expense_review_runs, workflow_run_feed
from nortpole.work.workflow_schedules.models import NortPoleWorkflowRun, NortPoleWorkflowSchedule
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")


def _add_run(
    db: Session,
    owner: User,
    filename: str,
    *,
    needs_review: bool | None = False,
    outcome: RunStatus = RunStatus.COMPLETE,
    deleted: bool = False,
    incognito: bool = False,
) -> int:
    chat = ChatSession(
        user_id=owner.id,
        deleted=deleted,
        incognito_record_mode=IncognitoRecordMode.FULL_HISTORY if incognito else None,
    )
    db.add(chat)
    db.flush()
    parent = ChatMessage(
        chat_session_id=chat.id,
        message_type=MessageType.USER,
        message="Review expenses",
        token_count=2,
        files=[{"id": "fixture", "type": "tabular", "name": filename}],
    )
    db.add(parent)
    db.flush()
    response = ChatMessage(
        chat_session_id=chat.id,
        parent_message_id=parent.id,
        message_type=MessageType.ASSISTANT,
        message="Result",
        token_count=1,
        receipt_review_needs_review=needs_review,
        response_status=outcome,
    )
    db.add(response)
    db.flush()
    return response.id


def test_expense_run_history_cursor_stays_inside_the_owners_visible_history() -> None:
    with get_session_with_current_tenant() as db:
        try:
            owner = User(email=f"{uuid4()}@example.invalid", hashed_password="fixture")
            other = User(email=f"{uuid4()}@example.invalid", hashed_password="fixture")
            db.add_all([owner, other])
            db.flush()
            first = _add_run(db, owner, "January.csv")
            second = _add_run(db, owner, "February.csv", needs_review=True)
            _add_run(db, owner, "Normal chat.csv", needs_review=None)
            _add_run(db, owner, "Deleted.csv", deleted=True)
            _add_run(db, owner, "Incognito.csv", incognito=True)
            _add_run(db, owner, "Running.csv", outcome=RunStatus.RUNNING)
            only_other = _add_run(db, other, "Private.csv")

            page = list_expense_review_runs(user=owner, db_session=db, page_size=1)
            assert [(r.id, r.file_name, r.status) for r in page.runs] == [
                (second, "February.csv", "needs_review")
            ]
            assert page.next_before_id == second
            older = list_expense_review_runs(
                user=owner, db_session=db, page_size=1, before_id=page.next_before_id
            )
            assert [(r.id, r.file_name, r.status) for r in older.runs] == [
                (first, "January.csv", "complete")
            ]
            assert older.next_before_id is None
            assert [r.id for r in list_expense_review_runs(user=other, db_session=db).runs] == [only_other]
        finally:
            db.rollback()


def test_unified_feed_merges_run_origins_and_deduplicates_linked_reviews() -> None:
    with get_session_with_current_tenant() as db:
        try:
            owner = User(email=f"{uuid4()}@example.invalid", hashed_password="fixture")
            other = User(email=f"{uuid4()}@example.invalid", hashed_password="fixture")
            db.add_all([owner, other])
            db.flush()
            manual_review = _add_run(db, owner, "Direct.csv", outcome=RunStatus.RUNNING)
            linked_review = _add_run(db, owner, "Scheduled.csv")
            linked_chat = db.get(ChatMessage, linked_review).chat_session_id
            _add_run(db, owner, "Incognito.csv", incognito=True)
            _add_run(db, other, "Other.csv")
            schedule = NortPoleWorkflowSchedule(
                owner_id=owner.id, name="Expense audit", title="Expense audit",
                request="Check expenses", cadence="daily", at_time="09:00", timezone="UTC",
            )
            db.add(schedule)
            db.flush()
            scheduled_rows = [
                NortPoleWorkflowRun(schedule_id=schedule.id, trigger="timer", outcome="queued"),
                NortPoleWorkflowRun(schedule_id=schedule.id, trigger="manual", outcome="running"),
                NortPoleWorkflowRun(schedule_id=schedule.id, trigger="chat", outcome="review_complete", chat_session_id=linked_chat),
            ]
            db.add_all(scheduled_rows)
            db.flush()

            first = workflow_run_feed(user=owner, db_session=db, page_size=2, before_key=None)
            cursor = first.next_before
            assert cursor is not None
            older = workflow_run_feed(
                user=owner, db_session=db, page_size=2, before_at=cursor.at, before_key=cursor.key,
            )
            entries = {row.id: row for row in (*first.runs, *older.runs)}
            assert set(entries) == {manual_review, *(row.id for row in scheduled_rows)}
            assert entries[manual_review].status == "running"
            assert entries[scheduled_rows[0].id].outcome == "queued"
            assert entries[scheduled_rows[2].id].chat_session_id == linked_chat
            assert entries[scheduled_rows[2].id].chat_message_id == linked_review
            assert entries[scheduled_rows[2].id].file_name == "Scheduled.csv"
            selected = workflow_run_feed(
                user=owner, db_session=db, page_size=1, before_key=None, include_run=scheduled_rows[0].id,
            )
            assert any(row.id == scheduled_rows[0].id for row in selected.runs)
            other_view = workflow_run_feed(
                user=other, db_session=db, before_key=None, include_run=scheduled_rows[0].id,
            )
            assert all(row.id != scheduled_rows[0].id for row in other_view.runs)
        finally:
            db.rollback()
