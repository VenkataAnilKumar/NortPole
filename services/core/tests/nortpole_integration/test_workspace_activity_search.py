"""Verify search result scopes with real Chat and Workflow records."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response

from nortpole.agents.models import RunStatus
from nortpole.configs.constants import MessageType
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import IncognitoRecordMode, Permission
from nortpole.db.models import (
    ChatMessage,
    ChatSession,
    User,
    User__UserGroup,
    UserGroup,
)
from nortpole.server.features.search.activity import (
    ActivitySearchRequest,
    search_workspace_activity,
)
from nortpole.work.workflow_schedules.api import list_shared
from nortpole.work.workflow_schedules.models import (
    NortPoleWorkflowRun,
    NortPoleWorkflowSchedule,
)
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")


def test_chat_message_and_workflow_run_access() -> None:
    tag = uuid4().hex
    term = "searchfixture" + tag
    now = datetime.now(timezone.utc)

    with get_session_with_current_tenant() as db:
        owner = User(
            email=f"activity-owner-{tag}@example.com",
            hashed_password="x",
            is_active=True,
            effective_permissions=[
                Permission.BASIC_ACCESS.value,
                Permission.READ_CHAT.value,
            ],
        )
        member = User(
            email=f"activity-member-{tag}@example.com",
            hashed_password="x",
            is_active=True,
            effective_permissions=[
                Permission.BASIC_ACCESS.value,
                Permission.READ_CHAT.value,
            ],
        )
        group = UserGroup(name=f"activity-{tag}", is_up_to_date=True)
        db.add_all([owner, member, group])
        db.flush()
        membership = User__UserGroup(user_id=member.id, user_group_id=group.id)
        db.add(membership)

        chat = ChatSession(user_id=owner.id, description="Visible fixture conversation")
        summary_chat = ChatSession(user_id=owner.id, description="Other conversation")
        deleted = ChatSession(user_id=owner.id, description=term, deleted=True)
        incognito = ChatSession(
            user_id=owner.id,
            description=term,
            incognito_record_mode=IncognitoRecordMode.FULL_HISTORY,
        )
        db.add_all([chat, summary_chat, deleted, incognito])
        db.flush()
        result = ChatMessage(
            chat_session_id=chat.id,
            message=f"The result covers {term}.",
            message_type=MessageType.ASSISTANT,
            token_count=10,
            response_status=RunStatus.COMPLETE,
            receipt_review_needs_review=False,
        )
        db.add_all(
            [
                result,
                ChatMessage(
                    chat_session_id=summary_chat.id,
                    message=term,
                    message_type=MessageType.SUMMARY,
                    token_count=4,
                ),
            ]
        )
        scheduled = NortPoleWorkflowSchedule(
            owner_id=owner.id,
            name=f"Scheduled {term}",
            title="Expense task",
            request="Run the test",
            cadence="daily",
            at_time="09:00",
            timezone="UTC",
            shared_with_groups=[group.name],
        )
        db.add(scheduled)
        db.flush()
        old_run = NortPoleWorkflowRun(
            schedule_id=scheduled.id,
            fired_at=now - timedelta(days=40),
            outcome="plan_failed",
            reason=f"The old run mentioned {term}.",
        )
        db.add(old_run)
        db.flush()

        def search(user: User, tab: str, *, token_scopes=None, **filters):
            response = Response()
            request = Request({"type": "http"})
            if token_scopes is not None:
                request.state.token_scopes = token_scopes
            payload = search_workspace_activity(
                ActivitySearchRequest(query=term, tab=tab, **filters),
                response,
                request,
                user,
                db,
            )
            assert response.headers["Cache-Control"] == "private, no-store"
            return payload

        (hit,) = search(owner, "chats").results
        assert hit.url == f"/app?chatId={chat.id}&message={result.id}"
        assert term in hit.excerpt
        assert search(member, "chats").results == []
        with pytest.raises(HTTPException) as token_denied:
            search(owner, "chats", token_scopes=[Permission.READ_SEARCH])
        assert token_denied.value.status_code == 403

        (shared,) = search(member, "workflows").results
        assert shared.url == f"/app/workflows/scheduled?schedule={scheduled.id}"
        assert [
            item.id
            for item in list_shared(user=member, db_session=db, include=scheduled.id)
        ] == [scheduled.id]
        assert not search(member, "workflows", source="scheduled_run").results

        (failed,) = search(
            owner, "workflows", source="scheduled_run", status="plan_failed"
        ).results
        assert (
            failed.url
            == f"/app/workflows/scheduled?schedule={scheduled.id}&run={old_run.id}"
        )
        assert not search(
            owner, "workflows", source="scheduled_run", updated_since=now
        ).results
        (report,) = search(owner, "workflows", source="expense_review").results
        assert report.url.endswith(f"&message={result.id}")

        page = search(owner, "workflows", page_size=1)
        assert page.next_cursor
        with pytest.raises(HTTPException) as borrowed:
            search(member, "workflows", cursor=page.next_cursor)
        assert borrowed.value.status_code == 410
        next_page = search(owner, "workflows", cursor=page.next_cursor, page_size=1)
        assert page.results[0].id != next_page.results[0].id

        db.delete(membership)
        db.flush()
        assert not search(member, "workflows").results
