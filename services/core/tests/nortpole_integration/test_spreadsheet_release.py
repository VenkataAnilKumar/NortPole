from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from nortpole.agents.models import RunStatus
from nortpole.chat.agent_preview import create_preview_chat
from nortpole.chat.agent_releases import (
    AgentPublishRequest,
    pinned_agent_release,
    publish_agent_release,
    save_agent_release_draft,
)
from nortpole.configs.constants import MessageType
from nortpole.db.agent_preview import AgentPilotKind, AgentPreviewDraft
from nortpole.db.chat import create_chat_session
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import LLMModelFlowType, Permission
from nortpole.db.llm import fetch_default_model
from nortpole.db.models import ChatMessage, Persona, User
from nortpole.governance.route_policy.enforce import check_route
from tests.nortpole_integration.test_tasks_flow import _up


pytestmark = pytest.mark.skipif(not _up(), reason="needs local PostgreSQL")


@pytest.mark.parametrize("pilot", ["spreadsheet-analysis", "meeting-recap"])
def test_input_only_agent_can_test_and_pin_a_release_without_knowledge(pilot: AgentPilotKind) -> None:
    suffix = uuid4().hex[:8]
    with get_session_with_current_tenant() as outer:
        with Session(bind=outer.connection(), join_transaction_mode="create_savepoint") as db:
            model = fetch_default_model(db, LLMModelFlowType.CHAT)
            if model is None or model.is_router or not check_route(db, model.id).allowed:
                pytest.skip("needs a fixed default Chat model on an allowed route")
            owner = User(
                email=f"input-only-{suffix}@example.invalid", hashed_password="unused",
                is_active=True, effective_permissions=[Permission.BASIC_ACCESS.value, Permission.ADD_AGENTS.value],
            )
            db.add(owner)
            db.flush()
            agent = Persona(user_id=owner.id, name=f"Agent {suffix}", description="Private fixture")
            db.add(agent)
            db.flush()
            draft = AgentPreviewDraft(
                name=agent.name, system_prompt="Analyze the supplied input.",
                model_configuration_id=model.id, pilot=pilot,
            )
            save_agent_release_draft(agent, draft, owner, db)
            preview = create_preview_chat(draft, agent.id, owner, db)
            assert preview.agent_preview is not None and preview.agent_preview.document_set_ids == []
            completed = ChatMessage(
                chat_session_id=preview.id, message_type=MessageType.ASSISTANT,
                response_status=RunStatus.COMPLETE, message="Completed agent fixture", token_count=4,
            )
            db.add(completed)
            db.flush()
            release = publish_agent_release(agent.id, AgentPublishRequest(
                preview_chat_id=preview.id, test_response_id=completed.id, expected_active_version=None,
            ), owner, db)
            chat = create_chat_session(db, "Input-only agent fixture", owner.id, agent.id)
            pinned = pinned_agent_release(chat, db)
            assert pinned is not None and pinned.version == release.version
            assert pinned.configuration.pilot == pilot
        outer.rollback()
