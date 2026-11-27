import hashlib
import json

from sqlalchemy.orm import Session

from nortpole.auth.permissions import has_permission
from nortpole.chat.prompt_utils import get_default_base_system_prompt
from nortpole.chat.reporting import REPORTING_RENDERER_REVISION
from nortpole.configs.app_configs import DISABLE_VECTOR_DB
from nortpole.configs.constants import DEFAULT_PERSONA_ID
from nortpole.db.agent_preview import AgentPreview, AgentPreviewDraft
from nortpole.db.agent_releases import active_agent_release
from nortpole.db.chat import create_chat_session
from nortpole.db.document_set import get_document_set_by_id_for_user
from nortpole.db.enums import LLMModelFlowType, Permission, PermissionAuthority
from nortpole.db.llm import fetch_default_model, fetch_model_configuration_by_id
from nortpole.db.models import ChatSession, Persona, User
from nortpole.db.persona import can_edit_persona, user_can_access_persona
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.enforce import check_route


def require_preview_access(persona: Persona, user: User, db: Session) -> None:
    if user.is_anonymous:
        allowed = False
    elif persona.id == DEFAULT_PERSONA_ID:
        allowed = has_permission(user, Permission.ADD_AGENTS) != PermissionAuthority.NONE
    else:
        allowed = not persona.builtin_persona and can_edit_persona(
            user,
            persona,
            db,
            is_editable=user_can_access_persona(db, persona.id, user, get_editable=True),
        )
    if not allowed:
        raise NortPoleError(
            NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
            "You no longer have access to test this agent configuration.",
        )


def preview_library_names(
    preview: AgentPreviewDraft, user: User, db: Session, *, allow_partial: bool = False,
) -> list[str]:
    if preview.document_set_ids and DISABLE_VECTOR_DB:
        raise NortPoleError(
            NortPoleErrorCode.FEATURE_DISABLED, "Knowledge search is disabled."
        )
    names = []
    for library_id in sorted(set(preview.document_set_ids)):
        library = get_document_set_by_id_for_user(
            db, library_id, user, get_editable=False
        )
        if library is None:
            if allow_partial:
                continue
            raise NortPoleError(
                NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
                "A library in this agent preview is unavailable.",
            )
        names.append(library.name)
    return names


def require_preview_model(
    model_id: int | None, persona: Persona, user: User, db: Session
) -> int:
    from nortpole.server.manage.llm.api import get_valid_model_configuration_ids_for_persona

    if model_id is None or model_id not in get_valid_model_configuration_ids_for_persona(
        persona, user, db
    ):
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT, "Choose an available chat model."
        )
    return model_id


def agent_configuration_fingerprint(snapshot: AgentPreview, db: Session) -> str:
    model = fetch_model_configuration_by_id(db, snapshot.model_configuration_id)
    if model is None or not model.is_visible or model.is_router or LLMModelFlowType.CHAT not in model.llm_model_flow_types:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Choose an available, fixed chat model for this test.")
    route = check_route(db, model.id)
    if not route.allowed:
        raise NortPoleError(NortPoleErrorCode.POLICY_BLOCKED, "The model route is blocked by workspace policy.")
    if snapshot.pack_source is not None:
        from nortpole.work.packs.chat_agents import validate_pack_chat_configuration

        manifest = validate_pack_chat_configuration(db, snapshot)
        assert manifest is not None
        if route.kind not in manifest.requires.route_kinds or route.data_class not in manifest.requires.data_classes:
            raise NortPoleError(NortPoleErrorCode.POLICY_BLOCKED, "The model route or data class is outside the signed pack requirements.")
    provider = model.llm_provider
    # Keep only a digest. Endpoint and version identify the route without reading credentials.
    configuration = snapshot.model_dump(mode="json")
    if snapshot.pilot is None:
        configuration.pop("pilot")
    if snapshot.pack_source is None:
        configuration.pop("pack_source")
    dependencies = {
        "configuration": configuration,
        "route": {"kind": route.kind, "data_class": route.data_class},
        "provider": [provider.id, provider.provider, provider.api_base, provider.api_version, provider.deployment_name],
        "model": [model.name, model.max_input_tokens, model.temperature_default, model.reasoning_effort_default, model.reasoning_effort_max],
        "base_prompt": get_default_base_system_prompt(db),
    }
    if snapshot.pilot == "reporting":
        dependencies["reporting_renderer_revision"] = REPORTING_RENDERER_REVISION
    return hashlib.sha256(json.dumps(dependencies, sort_keys=True).encode()).hexdigest()


def create_preview_chat(
    draft: AgentPreviewDraft, agent_id: int | None, user: User, db: Session
) -> ChatSession:
    persona = db.get(Persona, agent_id if agent_id is not None else DEFAULT_PERSONA_ID)
    if persona is None or (agent_id is not None and persona.id == DEFAULT_PERSONA_ID):
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Agent unavailable.")
    require_preview_access(persona, user, db)
    current = None
    if agent_id is not None:
        active = active_agent_release(db, agent_id)
        current = persona.agent_release_draft or (active.configuration if active else None)
        if current is not None and draft.pilot != current.pilot:
            raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Use the pilot type configured on this agent.")
    pack_source = current.pack_source if current is not None else None
    if draft.pack_source is not None and draft.pack_source != pack_source:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Use the pack source staged on this agent.")
    if pack_source is not None:
        from nortpole.work.packs.chat_agents import validate_pack_chat_configuration

        draft = draft.model_copy(update={"pack_source": pack_source})
        validate_pack_chat_configuration(db, draft, require_active=True)
    if draft.requires_knowledge and not draft.document_set_ids:
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Select at least one Knowledge library for this pilot.")
    preview_library_names(draft, user, db)
    model_id = draft.model_configuration_id
    if model_id is None:
        default_model = fetch_default_model(db, LLMModelFlowType.CHAT)
        model_id = default_model.id if default_model is not None else None
    model_id = require_preview_model(model_id, persona, user, db)
    snapshot = AgentPreview.model_validate({
        **draft.model_dump(), "model_configuration_id": model_id,
    })
    chat = create_chat_session(
        db, f"Agent preview · {snapshot.name}", user.id, persona.id,
        agent_preview=snapshot, agent_preview_fingerprint=agent_configuration_fingerprint(snapshot, db),
    )
    return chat
