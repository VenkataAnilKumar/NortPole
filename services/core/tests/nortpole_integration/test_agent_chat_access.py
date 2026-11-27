"""Existing Chat conversations follow current agent grants."""

from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from nortpole.chat.process_message import _load_session
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import ChatSession, Persona, Persona__User, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.query_and_chat.models import SendMessageRequest
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs PostgreSQL")


def test_removing_agent_share_blocks_next_turn_in_existing_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_files = Mock()
    monkeypatch.setattr("nortpole.chat.process_message.verify_user_files", verify_files)
    monkeypatch.setattr("nortpole.chat.process_message.mt_cloud_telemetry", Mock())
    with get_session_with_current_tenant() as outer:
        with Session(
            bind=outer.connection(), join_transaction_mode="create_savepoint"
        ) as db:
            owner, teammate = (
                User(email=f"{uuid4()}@example.invalid", hashed_password="fixture")
                for _ in range(2)
            )
            db.add_all([owner, teammate])
            db.flush()
            agent = Persona(
                name="Research QA",
                description="Checks agent grants",
                user_id=owner.id,
                is_public=False,
            )
            db.add(agent)
            db.flush()
            share = Persona__User(persona_id=agent.id, user_id=teammate.id)
            chat = ChatSession(user_id=teammate.id, persona_id=agent.id)
            db.add_all([share, chat])
            db.flush()
            request = SendMessageRequest(message="Follow-up", chat_session_id=chat.id)
            assert _load_session(request, teammate, db).id == chat.id

            db.delete(share)
            db.flush()
            with pytest.raises(NortPoleError) as denied:
                _load_session(request, teammate, db)
            assert denied.value.error_code == NortPoleErrorCode.INSUFFICIENT_PERMISSIONS
            assert "Start a new chat" in denied.value.detail
            verify_files.assert_called_once()
        outer.rollback()
