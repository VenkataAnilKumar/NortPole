"""Pack Chat releases and rollback inside one isolated PostgreSQL transaction."""

import base64
import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy.orm import Session

from nortpole.agents.models import RunStatus
from nortpole.chat.agent_preview import create_preview_chat
from nortpole.chat.agent_releases import (
    AgentPublishRequest,
    AgentRollbackRequest,
    pinned_agent_release,
    publish_agent_release,
    rollback_agent_release,
    save_agent_release_draft,
    validate_agent_release_dependencies,
)
from nortpole.configs.constants import MessageType
from nortpole.db.chat import create_chat_session
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import LLMModelFlowType, Permission
from nortpole.db.llm import fetch_default_model
from nortpole.db.models import ChatMessage, DocumentSet, Persona, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.enforce import check_route
from nortpole.work.packs.chat_agents import stage_pack_chat_agent
from nortpole.work.packs.manifest import Manifest, canonical_bytes
from nortpole.work.packs.models import NortPolePackSigner, NortPolePackVersion
from tests.nortpole_integration.test_tasks_flow import _up


pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the pack tables")

_SOURCE = Path(__file__).resolve().parents[4] / "packs/horizontal/everyday-brief/manifest.yaml"


@pytest.mark.parametrize("pilot", ["research", "reporting"])
def test_signed_pack_update_stages_same_agent_and_preserves_pinned_chat(pilot: str) -> None:
    suffix = uuid4().hex[:8]
    pack_id = f"chat-brief-{suffix}"
    with get_session_with_current_tenant() as outer:
        with Session(bind=outer.connection(), join_transaction_mode="create_savepoint") as db:
            model = fetch_default_model(db, LLMModelFlowType.CHAT)
            if model is None or model.is_router or not check_route(db, model.id).allowed:
                pytest.skip("needs a fixed default Chat model on an allowed route")
            route = check_route(db, model.id)
            owner = User(
                email=f"pack-chat-{suffix}@example.invalid",
                hashed_password="unused",
                is_active=True,
                effective_permissions=[Permission.ADD_AGENTS.value, Permission.BASIC_ACCESS.value],
            )
            library = DocumentSet(name=f"Pack Chat fixture {suffix}", is_public=True, is_up_to_date=True)
            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            signer = NortPolePackSigner(key_id=f"chat-{suffix}", public_key=base64.b64encode(public_key).decode())
            db.add_all([owner, library, signer])
            db.flush()

            def install(version: str, instructions: str) -> NortPolePackVersion:
                manifest = yaml.safe_load(_SOURCE.read_text(encoding="utf-8"))
                manifest.update(id=pack_id, version=version)
                manifest["requires"] = {"route_kinds": [route.kind], "data_classes": [route.data_class]}
                manifest["agents"][0]["instructions"] = instructions
                manifest["agents"][0]["chat_pilot"] = pilot
                signed = canonical_bytes(manifest)
                result = NortPolePackVersion(
                    pack_id=pack_id, version=version, active=True,
                    manifest=Manifest.model_validate(manifest).model_dump(mode="json"),
                    signed_manifest=signed.decode(), digest=hashlib.sha256(signed).hexdigest(),
                    signature=base64.b64encode(private_key.sign(signed)).decode(),
                    signer_key_id=signer.key_id,
                )
                db.add(result)
                db.flush()
                return result

            def tested_candidate(agent: Persona, version: int | None) -> AgentPublishRequest:
                draft = agent.agent_release_draft
                if draft is None:
                    draft = first_release.configuration
                preview = create_preview_chat(draft.model_copy(update={"pack_source": None}), agent.id, owner, db)
                assert preview.agent_preview is not None and preview.agent_preview.pack_source == draft.pack_source
                answer = ChatMessage(
                    chat_session_id=preview.id, message_type=MessageType.ASSISTANT,
                    response_status=RunStatus.COMPLETE, message="Completed test fixture", token_count=4,
                )
                db.add(answer)
                db.flush()
                return AgentPublishRequest(
                    preview_chat_id=preview.id, test_response_id=answer.id, expected_active_version=version,
                )

            first_pack = install("1.1.0", "Find evidence and cite it.")
            agent_id = stage_pack_chat_agent(db, owner, pack_id, first_pack.version, "evidence-research")
            assert stage_pack_chat_agent(db, owner, pack_id, first_pack.version, "evidence-research") == agent_id
            agent = db.get(Persona, agent_id)
            assert agent is not None and not agent.is_public and agent.agent_release_draft is not None
            draft = agent.agent_release_draft.model_copy(update={
                "document_set_ids": [library.id], "model_configuration_id": model.id,
            })
            assert draft.pilot == pilot
            with pytest.raises(NortPoleError, match="signed pack"):
                save_agent_release_draft(agent, draft.model_copy(update={"system_prompt": "Changed instructions"}), owner, db)
            save_agent_release_draft(agent, draft, owner, db)
            first_release = publish_agent_release(agent_id, tested_candidate(agent, None), owner, db)
            assert first_release.configuration.pack_source.version == "1.1.0"
            existing = create_chat_session(db, "Old version chat", owner.id, agent_id)
            stale_test = tested_candidate(agent, 1)

            first_pack.active = False
            next_pack = install("1.2.0", "Find evidence, cite it, and identify missing facts.")
            with pytest.raises(NortPoleError, match="current pack version"):
                publish_agent_release(agent_id, stale_test, owner, db)

            assert stage_pack_chat_agent(db, owner, pack_id, next_pack.version, "evidence-research") == agent_id
            assert agent.agent_release_draft is not None
            assert agent.agent_release_draft.document_set_ids == [library.id]
            assert pinned_agent_release(existing, db).version == 1
            second = publish_agent_release(agent_id, tested_candidate(agent, 1), owner, db)
            assert second.configuration.pack_source.version == "1.2.0"
            recent = create_chat_session(db, "New version chat", owner.id, agent_id)
            assert pinned_agent_release(existing, db).version == 1
            assert pinned_agent_release(recent, db).version == 2
            restored = rollback_agent_release(
                agent_id, AgentRollbackRequest(version=1, expected_active_version=2), owner, db,
            )
            assert restored.configuration.pack_source.version == "1.1.0"
            with pytest.raises(NortPoleError, match="Start a new chat"):
                pinned_agent_release(recent, db)

            signer.revoked = True
            db.flush()
            previous = pinned_agent_release(existing, db)
            with pytest.raises(NortPoleError) as rejected:
                validate_agent_release_dependencies(previous.configuration, previous.dependency_fingerprint, agent, owner, db)
            assert rejected.value.error_code == NortPoleErrorCode.POLICY_BLOCKED
        outer.rollback()

    with get_session_with_current_tenant() as db:
        assert db.get(Persona, agent_id) is None
