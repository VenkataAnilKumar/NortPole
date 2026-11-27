from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from nortpole.configs.constants import DocumentSource, MessageType
from nortpole.connectors.models import InputType
from nortpole.db.chat import create_new_chat_message, get_chat_session_by_id, get_or_create_root_message, update_chat_session
from nortpole.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant
from nortpole.db.enums import (
    AccessType,
    ChatSessionSharedStatus,
    IncognitoRecordMode,
    ConnectorCredentialPairStatus,
    IndexingMode,
    Permission,
)
from nortpole.db.models import (
    ChatSession,
    Connector,
    ConnectorCredentialPair,
    Credential,
    DocumentSet,
    DocumentSet__ConnectorCredentialPair,
    DocumentSet__UserGroup,
    Project__UserFile,
    User,
    UserGroup,
    UserGroup__CCPairDataAccess,
    UserFile,
    UserProject,
)
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.features.document_set import output_contributions
from nortpole.server.features.projects import api, collaboration, outputs
from nortpole.chat.chat_utils import create_chat_session_from_request
from nortpole.server.query_and_chat.models import ChatSessionCreationRequest


@pytest.fixture
def db():
    try:
        SqlEngine.init_engine(pool_size=2, max_overflow=0)
        session_context = get_session_with_current_tenant()
        with session_context as check_db:
            check_db.execute(text("select 1 from project_output limit 1"))
    except Exception:
        pytest.skip("needs the Project outputs migration on PostgreSQL")
    with get_session_with_current_tenant() as outer:
        with Session(
            bind=outer.connection(), join_transaction_mode="create_savepoint"
        ) as inner:
            yield inner
        outer.rollback()


def user(db: Session, *, admin: bool = False) -> User:
    item = User(
        email=f"{uuid4()}@example.invalid",
        hashed_password="fixture",
        effective_permissions=[Permission.FULL_ADMIN_PANEL_ACCESS.value]
        if admin
        else [],
    )
    db.add(item)
    db.flush()
    return item


def test_owner_can_save_and_retry_and_stale_updates_are_rejected(db: Session) -> None:
    owner = user(db)
    other = user(db, admin=True)
    project = UserProject(user_id=owner.id, name="Output regression")
    db.add(project)
    db.flush()
    output_id = uuid4()
    original = outputs.SaveOutput(
        name="Findings",
        version=0,
        artifact=outputs.Document(
            kind="document", payload=outputs.DocumentPayload(body="# Findings")
        ),
    )
    assert outputs.save_output(project.id, output_id, original, owner, db).version == 1
    assert outputs.save_output(project.id, output_id, original, owner, db).version == 1

    with pytest.raises(HTTPException) as denied:
        outputs.get_output(project.id, output_id, other, db)
    assert denied.value.status_code == 404
    stale = original.model_copy(update={"name": "Stale edit"})
    with pytest.raises(HTTPException) as conflict:
        outputs.save_output(project.id, output_id, stale, owner, db)
    assert conflict.value.status_code == 409
    update = stale.model_copy(update={"name": "Revised findings", "version": 1})
    assert outputs.save_output(project.id, output_id, update, owner, db).version == 2
    assert [item.name for item in outputs.list_outputs(project.id, owner, db)] == [
        "Revised findings"
    ]


def test_knowledge_contribution_requires_matching_dedicated_source(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin, outsider = user(db, admin=True), user(db)
    label = uuid4().hex
    group = UserGroup(name=f"output-group-{label}", is_up_to_date=True)
    collection = DocumentSet(
        name=f"output-collection-{label}", is_public=False, is_up_to_date=True
    )
    connector = Connector(
        name=f"output-source-{label}",
        source=DocumentSource.FILE,
        input_type=InputType.LOAD_STATE,
        connector_specific_config={"file_locations": []},
    )
    credential = Credential(
        name=f"output-credential-{label}",
        source=DocumentSource.FILE,
        credential_json={},
    )
    db.add_all([group, collection, connector, credential])
    db.flush()
    pair = ConnectorCredentialPair(
        name=f"output-pair-{label}",
        status=ConnectorCredentialPairStatus.ACTIVE,
        access_type=AccessType.PUBLIC,
        connector_id=connector.id,
        credential_id=credential.id,
    )
    db.add(pair)
    db.flush()
    db.add(
        DocumentSet__UserGroup(document_set_id=collection.id, user_group_id=group.id)
    )
    db.add(
        DocumentSet__ConnectorCredentialPair(
            document_set_id=collection.id,
            connector_credential_pair_id=pair.id,
            is_current=True,
        )
    )
    db.commit()
    store = Mock()
    store.has_file.return_value = False
    monkeypatch.setattr(output_contributions, "DISABLE_VECTOR_DB", False)
    monkeypatch.setattr(output_contributions, "get_default_file_store", lambda: store)
    body = output_contributions.Contribution(
        name="QA summary", text="# Findings", format="md", audience_key="0" * 64
    )

    assert collection.id not in {
        item.id for item in output_contributions.destinations(admin, db)
    }
    with pytest.raises(HTTPException) as mismatch:
        output_contributions.contribute_output(collection.id, body, admin, db)
    assert mismatch.value.status_code == 409
    store.save_file.assert_not_called()
    pair.access_type = AccessType.PRIVATE
    db.flush()
    db.add(
        UserGroup__CCPairDataAccess(
            cc_pair_id=pair.id, user_group_id=group.id, access_type=AccessType.PRIVATE
        )
    )
    db.commit()
    destination = next(
        item
        for item in output_contributions.destinations(admin, db)
        if item.id == collection.id
    )
    with pytest.raises(HTTPException) as stale_audience:
        output_contributions.contribute_output(collection.id, body, admin, db)
    assert stale_audience.value.status_code == 409
    store.save_file.assert_not_called()
    body = body.model_copy(update={"audience_key": destination.audience_key})
    with pytest.raises(HTTPException) as denied:
        output_contributions.contribute_output(collection.id, body, outsider, db)
    assert denied.value.status_code in (403, 404)
    assert output_contributions.contribute_output(collection.id, body, admin, db) == {
        "name": "QA summary.md"
    }
    assert output_contributions.contribute_output(collection.id, body, admin, db) == {
        "name": "QA summary.md"
    }
    store.save_file.assert_called_once()
    assert store.save_file.call_args.args[0].getvalue() == b"# Findings"
    assert pair.indexing_trigger == IndexingMode.UPDATE
    assert len(connector.connector_specific_config["file_locations"]) == 1

def test_moving_chat_keeps_sharing_and_rejects_hidden_or_other_users_chats(db: Session) -> None:
    owner, other = user(db), user(db)
    source = UserProject(user_id=owner.id, name="Source project")
    target = UserProject(user_id=owner.id, name="Target project")
    other_project = UserProject(user_id=other.id, name="Other project")
    db.add_all([source, target, other_project])
    db.flush()

    chat = ChatSession(
        user_id=owner.id, project_id=source.id, shared_status=ChatSessionSharedStatus.PUBLIC
    )
    hidden = ChatSession(
        user_id=owner.id, project_id=source.id, incognito_record_mode=IncognitoRecordMode.FULL_HISTORY
    )
    deleted = ChatSession(user_id=owner.id, project_id=source.id, deleted=True)
    db.add_all([chat, hidden, deleted])
    db.flush()
    body = api.ChatSessionRequest(chat_session_id=str(chat.id))

    with pytest.raises(HTTPException) as error:
        api.move_chat_session(other_project.id, body, owner, db)
    assert error.value.status_code == 404
    with pytest.raises(NortPoleError) as error:
        api.move_chat_session(other_project.id, body, other, db)
    assert error.value.status_code == 404

    for session in (hidden, deleted):
        unusable = api.ChatSessionRequest(chat_session_id=str(session.id))
        with pytest.raises(NortPoleError) as error:
            api.move_chat_session(target.id, unusable, owner, db)
        assert error.value.status_code == 404
        with pytest.raises(NortPoleError) as error:
            api.remove_chat_session(unusable, owner, db)
        assert error.value.status_code == 404
        assert session.project_id == source.id

    assert api.move_chat_session(target.id, body, owner, db).status_code == 204
    assert chat.project_id == target.id
    assert chat.shared_status == ChatSessionSharedStatus.PUBLIC
    assert api.remove_chat_session(body, owner, db).status_code == 204
    assert chat.project_id is None
    assert chat.shared_status == ChatSessionSharedStatus.PUBLIC


def test_create_project_and_move_commits_both_or_neither(db: Session) -> None:
    owner = user(db)
    chat = ChatSession(user_id=owner.id)
    hidden = ChatSession(user_id=owner.id, incognito_record_mode=IncognitoRecordMode.FULL_HISTORY)
    db.add_all([chat, hidden])
    db.commit()

    with pytest.raises(NortPoleError) as error:
        api.create_project("Rejected move", owner, db, chat_session_id=str(hidden.id))
    assert error.value.status_code == 404
    assert db.scalar(select(UserProject).where(UserProject.user_id == owner.id)) is None

    project = api.create_project("Confirmed move", owner, db, chat_session_id=str(chat.id))
    assert chat.project_id == project.id
    assert [item.id for item in project.chat_sessions] == [chat.id]

def test_project_roles_and_revocation_cover_direct_resource_links(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, viewer, editor, outsider = user(db), user(db), user(db), user(db, admin=True)
    project = api.create_project("Shared QA", owner, db)
    project_id = project.id
    chat = ChatSession(user_id=owner.id, project_id=project_id, description="Internal review")
    hidden = ChatSession(
        user_id=owner.id, project_id=project_id, incognito_record_mode=IncognitoRecordMode.FULL_HISTORY
    )
    private_file = UserFile(
        id=uuid4(), user_id=owner.id, file_id="project-file", name="project.txt",
        file_type="text/plain",
    )
    unrelated_file = UserFile(
        id=uuid4(), user_id=owner.id, file_id="unrelated-file", name="personal.txt",
        file_type="text/plain",
    )
    db.add_all([chat, hidden, private_file, unrelated_file])
    db.flush()
    db.add(Project__UserFile(project_id=project_id, user_file_id=private_file.id))
    root = get_or_create_root_message(chat.id, db)
    create_new_chat_message(chat.id, root, "Shareable project message", 10, MessageType.USER, db)
    output_id = uuid4()
    saved = outputs.SaveOutput(
        name="Summary",
        version=0,
        artifact=outputs.Document(kind="document", payload=outputs.DocumentPayload(body="Shared notes")),
    )
    outputs.save_output(project_id, output_id, saved, owner, db)
    store = Mock()
    store.read_file.return_value = iter([b"project data"])
    monkeypatch.setattr(collaboration, "get_default_file_store", lambda: store)

    for person, role in ((viewer, "viewer"), (editor, "editor")):
        assert collaboration.add_member(
            project_id, collaboration.MemberRequest(email=person.email.upper(), role=role), owner, db
        ).role == role
    assert {member.user_id for member in collaboration.list_members(project_id, Response(), owner, db)} == {viewer.id, editor.id}
    assert api.get_projects(viewer, db)[0].role == "viewer"
    assert api.get_projects(outsider, db) == []

    for person in (viewer, editor):
        details = api.get_project_details(project_id, person, db)
        assert details.project.shared
        assert [(item.id, item.is_owned) for item in details.project.chat_sessions] == [(chat.id, False)]
        assert details.files is not None and [item.id for item in details.files] == [private_file.id]
        transcript = collaboration.get_project_transcript(project_id, chat.id, Response(), user=person, db=db)
        assert [item.text for item in transcript.messages] == ["Shareable project message"]
        assert outputs.get_output(project_id, output_id, person, db).artifact == saved.artifact
        assert collaboration.download_project_file(project_id, private_file.id, person, db).headers["cache-control"] == "private, no-store"
        with pytest.raises(HTTPException, match="404"):
            collaboration.download_project_file(project_id, unrelated_file.id, person, db)
        with pytest.raises(HTTPException, match="404"):
            collaboration.get_project_transcript(project_id, hidden.id, Response(), user=person, db=db)
        with pytest.raises(ValueError):
            get_chat_session_by_id(chat.id, person.id, db)

    with pytest.raises(HTTPException, match="403"):
        collaboration.remove_member(project_id, viewer.id, editor, db)
    with pytest.raises(HTTPException, match="403"):
        api.upsert_project_instructions(project_id, api.UpsertProjectInstructionsRequest(instructions="Viewer edit"), viewer, db)
    with pytest.raises(HTTPException, match="403"):
        outputs.save_output(project_id, output_id, saved, viewer, db)
    with pytest.raises(HTTPException, match="403"):
        create_chat_session_from_request(ChatSessionCreationRequest(project_id=project_id, persona_id=0), viewer, db)
    assert api.upsert_project_instructions(project_id, api.UpsertProjectInstructionsRequest(instructions="Editor edit"), editor, db).instructions == "Editor edit"
    assert outputs.save_output(project_id, output_id, saved.model_copy(update={"name": "Edited", "version": 1}), editor, db).version == 2
    editor_file = UserFile(
        id=uuid4(), user_id=editor.id, file_id="contributed-file", name="contributed.txt",
        file_type="text/plain",
    )
    db.add(editor_file)
    db.flush()
    monkeypatch.setattr(api, "_trigger_user_file_project_sync", lambda *_: None)
    with pytest.raises(HTTPException, match="403"):
        api.unlink_user_file_from_project(project_id, private_file.id, BackgroundTasks(), viewer, db)
    with pytest.raises(HTTPException, match="404"):
        api.link_user_file_to_project(project_id, unrelated_file.id, BackgroundTasks(), editor, db)
    assert api.link_user_file_to_project(project_id, editor_file.id, BackgroundTasks(), editor, db).id == editor_file.id
    assert {item.id for item in api.get_files_in_project(project_id, viewer, db)} == {private_file.id, editor_file.id}
    authored = create_chat_session_from_request(ChatSessionCreationRequest(project_id=project_id, persona_id=0), editor, db)
    assert authored.project_id == project_id
    with pytest.raises(NortPoleError, match="project access"):
        update_chat_session(db, owner.id, chat.id, sharing_status=ChatSessionSharedStatus.PUBLIC)

    collaboration.change_member_role(project_id, editor.id, collaboration.RoleRequest(role="viewer"), owner, db)
    assert authored.project_id is None
    with pytest.raises(HTTPException, match="404"):
        collaboration.get_project_transcript(project_id, authored.id, Response(), user=owner, db=db)

    for person in (viewer, editor):
        collaboration.remove_member(project_id, person.id, owner, db)
        for actor in (person, outsider):
            with pytest.raises(HTTPException, match="404"):
                api.get_project_details(project_id, actor, db)
            with pytest.raises(HTTPException, match="404"):
                collaboration.get_project_transcript(project_id, chat.id, Response(), user=actor, db=db)
            with pytest.raises(HTTPException, match="404"):
                collaboration.download_project_file(project_id, private_file.id, actor, db)
            with pytest.raises(HTTPException, match="404"):
                outputs.get_output(project_id, output_id, actor, db)
    assert api.get_project(project_id, owner, db).shared is False
    assert {item.id for item in api.get_files_in_project(project_id, owner, db)} == {private_file.id, editor_file.id}


def test_project_with_public_chat_requires_unsharing_before_add(db: Session) -> None:
    owner, recipient = user(db), user(db)
    project = api.create_project("Private QA", owner, db)
    db.add(ChatSession(user_id=owner.id, project_id=project.id, shared_status=ChatSessionSharedStatus.PUBLIC))
    db.flush()

    with pytest.raises(HTTPException, match="Turn off public sharing"):
        collaboration.add_member(project.id, collaboration.MemberRequest(email=recipient.email, role="viewer"), owner, db)
    assert api.get_projects(recipient, db) == []
