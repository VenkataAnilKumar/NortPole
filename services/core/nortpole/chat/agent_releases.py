from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from pydantic import BaseModel, Field, StrictBool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nortpole.agents.models import RunStatus
from nortpole.auth.permissions import has_global_permission
from nortpole.chat.agent_preview import (
    agent_configuration_fingerprint,
    preview_library_names,
    require_preview_access,
    require_preview_model,
)
from nortpole.configs.constants import DEFAULT_PERSONA_ID, MessageType
from nortpole.db.agent_preview import AgentPreview, AgentPreviewDraft
from nortpole.db.agent_releases import active_agent_release, lock_agent_release_state
from nortpole.db.enums import LLMModelFlowType, Permission
from nortpole.db.llm import fetch_default_model
from nortpole.db.models import AgentRelease, ChatMessage, ChatSession, Persona, User
from nortpole.db.persona import can_delete_persona
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.audit import record_audit
from nortpole.tools.constants import SEARCH_TOOL_ID
from nortpole.utils.audit import AuditAction, AuditOutcome


class AgentReleaseAction(BaseModel, extra="forbid"):
    expected_active_version: int | None = Field(ge=1)


class AgentPublishRequest(AgentReleaseAction):
    preview_chat_id: UUID
    test_response_id: int = Field(gt=0)
    expected_next_version: int | None = Field(default=None, ge=1)
    expected_audience_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class AgentRollbackRequest(AgentReleaseAction):
    version: int = Field(gt=0)


class AgentVerificationRequest(BaseModel, extra="forbid"):
    version: int = Field(gt=0)
    verified: StrictBool


class AgentReleaseDetails(BaseModel, from_attributes=True):
    version: int
    configuration: AgentPreview
    test_chat_id: UUID
    test_response_id: int
    tested_by: UUID
    tested_at: datetime
    published_by: UUID
    published_at: datetime
    is_active: bool
    withdrawn_at: datetime | None
    verified_at: datetime | None = None
    verified_by: UUID | None = None


class AgentTestDetails(BaseModel):
    chat_id: UUID
    response_id: int
    configuration: AgentPreview
    tested_by: UUID
    tested_at: datetime
    own_chat: bool
    matches_draft: bool


class AgentReleaseState(BaseModel):
    can_publish: bool
    can_verify: bool = False
    company_listed: bool = False
    active_version: int | None
    next_version: int
    draft: AgentPreviewDraft | None
    versions: list[AgentReleaseDetails]
    tests: list[AgentTestDetails]
    enrollment_blocked: bool
    audience: str
    audience_revision: str | None = None
    shared_with: list[str] = Field(default_factory=list)


def _eligible_persona(persona: Persona) -> bool:
    return not (persona.user_files or persona.attached_documents or persona.hierarchy_nodes) and all(
        tool.in_code_tool_id == SEARCH_TOOL_ID for tool in persona.tools
    )


def _release_persona(persona_id: int, user: User, db: Session, *, publish: bool = False) -> Persona:
    persona = db.get(Persona, persona_id, with_for_update=True, populate_existing=True) if publish else db.get(Persona, persona_id)
    if persona_id == DEFAULT_PERSONA_ID or persona is None or persona.deleted or persona.builtin_persona:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Agent unavailable.")
    permitted = can_delete_persona(user, persona, db) and not user.is_anonymous
    if publish and not permitted:
        raise NortPoleError(NortPoleErrorCode.INSUFFICIENT_PERMISSIONS, "Only the agent owner or an agent administrator can publish versions.")
    if not permitted:
        require_preview_access(persona, user, db)
    return persona


def _completed_preview_responses():
    return (
        select(ChatMessage.id, ChatMessage.chat_session_id, ChatMessage.time_sent)
        .where(ChatMessage.message_type == MessageType.ASSISTANT)
        .where(ChatMessage.invoking_tool_call_id.is_(None))
        .where(ChatMessage.response_status == RunStatus.COMPLETE)
        .where(func.length(func.trim(ChatMessage.message)) > 0)
    )


def _resolved_draft(persona: Persona, db: Session) -> AgentPreviewDraft | None:
    draft = persona.agent_release_draft
    if draft is None or draft.model_configuration_id is not None:
        return draft
    model = fetch_default_model(db, LLMModelFlowType.CHAT)
    return draft.model_copy(update={"model_configuration_id": model.id if model else None})


def _matches_draft(draft: AgentPreviewDraft | None, snapshot: AgentPreview) -> bool:
    return draft is None or draft.model_dump(mode="json") == snapshot.model_dump(mode="json")


def _audience_revision(persona: Persona) -> str:
    grants = sorted(
        [f"user:{share.user_id}:{share.permission}" for share in persona.user_shares]
        + [f"group:{share.user_group_id}:{share.permission}" for share in persona.group_shares]
    )
    access = [str(persona.user_id), str(persona.owner_group_id), str(persona.is_public), str(persona.public_permission)]
    return sha256("|".join(access + grants).encode()).hexdigest()


def get_agent_release_state(persona_id: int, user: User, db: Session) -> AgentReleaseState:
    persona = _release_persona(persona_id, user, db)
    can_publish = can_delete_persona(user, persona, db)
    versions = db.scalars(select(AgentRelease).where(AgentRelease.persona_id == persona_id).order_by(AgentRelease.version.desc())).all()
    responses = _completed_preview_responses().subquery()
    previews = (
        select(ChatSession, responses.c.id, responses.c.time_sent)
        .join(responses, responses.c.chat_session_id == ChatSession.id)
        .where(ChatSession.persona_id == persona_id, ChatSession.deleted.is_(False), ChatSession.agent_preview_fingerprint.is_not(None))
        .where(responses.c.id == select(func.max(responses.c.id)).where(responses.c.chat_session_id == ChatSession.id).correlate(ChatSession).scalar_subquery())
        .where(~ChatSession.id.in_(select(AgentRelease.test_chat_id).where(AgentRelease.persona_id == persona_id)))
        .order_by(responses.c.id.desc())
        .limit(20)
    )
    if not can_publish:
        previews = previews.where(ChatSession.user_id == user.id)
    completed_tests = db.execute(previews).all()
    draft = _resolved_draft(persona, db) if completed_tests else None
    shared_with = []
    if can_publish and not persona.is_public:
        shared_with = sorted(
            [share.user.email for share in persona.user_shares if share.user and share.user.email]
            + [share.user_group.name for share in persona.group_shares if share.user_group]
        )
    return AgentReleaseState(
        can_publish=can_publish,
        can_verify=has_global_permission(user, Permission.MANAGE_AGENTS) and not user.is_anonymous,
        company_listed=persona.is_public and persona.is_listed,
        active_version=next((row.version for row in versions if row.is_active), None),
        next_version=versions[0].version + 1 if versions else 1,
        draft=persona.agent_release_draft,
        versions=[AgentReleaseDetails.model_validate(row) for row in versions],
        tests=[
            AgentTestDetails(
                chat_id=chat.id, response_id=response_id, configuration=chat.agent_preview,
                tested_by=chat.user_id, tested_at=tested_at, own_chat=chat.user_id == user.id,
                matches_draft=_matches_draft(draft, chat.agent_preview),
            )
            for chat, response_id, tested_at in completed_tests
            if chat.agent_preview is not None and chat.user_id is not None
        ],
        enrollment_blocked=not _eligible_persona(persona),
        audience="Organization" if persona.is_public else "Shared" if persona.user_shares or persona.group_shares else "Private",
        audience_revision=_audience_revision(persona) if can_publish else None,
        shared_with=shared_with,
    )


def save_agent_release_draft(persona: Persona, draft: AgentPreviewDraft, user: User, db: Session) -> None:
    require_preview_access(persona, user, db)
    if draft.requires_knowledge and not draft.document_set_ids:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Select at least one Knowledge library for this pilot.")
    preview_library_names(draft, user, db)
    if draft.model_configuration_id is not None:
        require_preview_model(draft.model_configuration_id, persona, user, db)
    if draft.pack_source is not None:
        from nortpole.work.packs.chat_agents import validate_pack_chat_configuration

        validate_pack_chat_configuration(db, draft, require_active=True)
    persona.agent_release_draft = draft
    db.commit()


def _expected_release(db: Session, persona_id: int, expected: int | None) -> AgentRelease | None:
    active = active_agent_release(db, persona_id)
    if (active.version if active else None) != expected:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The active version changed. Refresh version history and try again.")
    return active


def validate_agent_release_dependencies(
    snapshot: AgentPreview, fingerprint: str, persona: Persona, user: User, db: Session,
    *, allow_partial_libraries: bool = False,
) -> list[str]:
    names = preview_library_names(snapshot, user, db, allow_partial=allow_partial_libraries)
    require_preview_model(snapshot.model_configuration_id, persona, user, db)
    if agent_configuration_fingerprint(snapshot, db) != fingerprint:
        if snapshot.pilot == "reporting":
            raise NortPoleError(NortPoleErrorCode.CONFLICT, "Reporting or its dependencies changed. Test the configuration again.")
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The agent's model route or workspace prompt changed. Test the configuration again.")
    return names


def publish_agent_release(persona_id: int, request: AgentPublishRequest, user: User, db: Session) -> AgentReleaseDetails:
    persona = _release_persona(persona_id, user, db, publish=True)
    active = _expected_release(db, persona_id, request.expected_active_version)
    if request.expected_audience_revision is not None and request.expected_audience_revision != _audience_revision(persona):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Agent access changed. Review the current audience and try again.")
    if not _eligible_persona(persona):
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Remove uploaded files, direct attachments, and actions from the saved agent before enabling versioned publishing.")
    chat = db.get(ChatSession, request.preview_chat_id)
    if chat is None or chat.persona_id != persona_id or chat.deleted or chat.agent_preview is None or not chat.agent_preview_fingerprint or chat.user_id is None:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose a completed test from this agent.")
    response = db.execute(_completed_preview_responses().where(ChatMessage.id == request.test_response_id, ChatMessage.chat_session_id == chat.id)).one_or_none()
    if response is None:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Run the preview successfully before publishing.")
    snapshot = chat.agent_preview
    if not _matches_draft(_resolved_draft(persona, db), snapshot):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The saved draft differs from this test. Test the draft before publishing.")
    duplicate = db.scalar(select(AgentRelease.id).where(AgentRelease.persona_id == persona_id, AgentRelease.test_chat_id == chat.id))
    if duplicate is not None:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This preview already has a version.")
    if snapshot.pack_source is not None:
        from nortpole.work.packs.chat_agents import validate_pack_chat_configuration

        validate_pack_chat_configuration(db, snapshot, require_active=True)
    validate_agent_release_dependencies(snapshot, chat.agent_preview_fingerprint, persona, user, db)
    last_version = db.scalar(select(func.max(AgentRelease.version)).where(AgentRelease.persona_id == persona_id)) or 0
    if request.expected_next_version is not None and request.expected_next_version != last_version + 1:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Version history changed. Review the tested version and try again.")
    if active is not None:
        active.is_active = False
        db.flush()
    release = AgentRelease(
        persona_id=persona_id, version=last_version + 1, configuration=snapshot,
        dependency_fingerprint=chat.agent_preview_fingerprint,
        test_chat_id=chat.id, test_response_id=response.id, tested_by=chat.user_id, tested_at=response.time_sent,
        published_by=user.id, published_at=datetime.now(timezone.utc), is_active=True,
    )
    db.add(release)
    persona.agent_release_draft = None
    db.commit()
    return AgentReleaseDetails.model_validate(release)


def rollback_agent_release(persona_id: int, request: AgentRollbackRequest, user: User, db: Session) -> AgentReleaseDetails:
    persona = _release_persona(persona_id, user, db, publish=True)
    active = _expected_release(db, persona_id, request.expected_active_version)
    target = db.scalar(select(AgentRelease).where(AgentRelease.persona_id == persona_id, AgentRelease.version == request.version))
    if active is None or target is None or target.is_active or target.withdrawn_at is not None or target.version >= active.version:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose an earlier eligible version to restore.")
    validate_agent_release_dependencies(target.configuration, target.dependency_fingerprint, persona, user, db)
    active.is_active = False
    active.withdrawn_at = datetime.now(timezone.utc)
    active.withdrawn_by = user.id
    db.flush()
    target.is_active = True
    db.commit()
    return AgentReleaseDetails.model_validate(target)


def set_agent_verification(
    persona_id: int, request: AgentVerificationRequest, user: User, db: Session,
) -> AgentReleaseDetails:
    if user.is_anonymous or not has_global_permission(user, Permission.MANAGE_AGENTS):
        raise NortPoleError(NortPoleErrorCode.INSUFFICIENT_PERMISSIONS)
    persona = _release_persona(persona_id, user, db, publish=True)
    release = db.scalar(select(AgentRelease).where(
        AgentRelease.persona_id == persona_id, AgentRelease.version == request.version,
    ))
    if release is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Agent version unavailable.")
    if request.verified:
        if not release.is_active or release.withdrawn_at is not None:
            raise NortPoleError(NortPoleErrorCode.CONFLICT, "The active version changed. Refresh version history.")
        if not persona.is_public or not persona.is_listed:
            raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "The agent must be listed for the organization.")
        validate_agent_release_dependencies(release.configuration, release.dependency_fingerprint, persona, user, db)
    if (release.verified_at is not None) == request.verified:
        return AgentReleaseDetails.model_validate(release)

    release.verified_at = datetime.now(timezone.utc) if request.verified else None
    release.verified_by = user.id if request.verified else None
    result = AgentReleaseDetails.model_validate(release)
    db.commit()
    record_audit(
        AuditAction.AGENT_VERIFICATION_CHANGE,
        AuditOutcome.SUCCESS,
        actor=user,
        summary=f"Agent version {result.version} verification {'granted' if request.verified else 'removed'}",
        resource_type="agent",
        resource_id=persona_id,
        details={"version": result.version, "verified": request.verified},
    )
    return result


def pinned_agent_release(chat: ChatSession, db: Session) -> AgentRelease | None:
    if chat.persona_id is None or chat.persona_id == DEFAULT_PERSONA_ID or chat.agent_preview is not None:
        return None
    lock_agent_release_state(db, chat.persona_id, read=True)
    if chat.agent_release_id is None:
        if active_agent_release(db, chat.persona_id) is None:
            if chat.persona and chat.persona.agent_release_draft and chat.persona.agent_release_draft.pilot:
                raise NortPoleError(NortPoleErrorCode.CONFLICT, "Run Test in Chat and publish the pilot before starting a regular chat.")
            return None
    else:
        release = db.get(AgentRelease, chat.agent_release_id, populate_existing=True)
        if release is not None and release.persona_id == chat.persona_id and release.withdrawn_at is None:
            return release
    raise NortPoleError(NortPoleErrorCode.CONFLICT, "This chat's agent version is unavailable. Start a new chat to use the active version.")
