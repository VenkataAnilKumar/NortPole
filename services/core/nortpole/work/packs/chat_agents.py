"""Stage signed, read-only pack agents on the Chat release lifecycle."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nortpole.db.agent_preview import AgentPreviewDraft, PackAgentSource
from nortpole.db.agent_releases import active_agent_release
from nortpole.db.models import Persona, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.work.packs.integrity import check_version
from nortpole.work.packs.manifest import AgentSpec, Manifest
from nortpole.work.packs.models import NortPolePackSigner, NortPolePackVersion


def pack_chat_definition(
    db: Session, source: PackAgentSource, *, require_active: bool = False,
) -> tuple[Manifest, AgentSpec]:
    stmt = select(NortPolePackVersion).where(
        NortPolePackVersion.pack_id == source.pack_id,
        NortPolePackVersion.version == source.version,
    )
    if require_active:
        stmt = stmt.with_for_update(read=True).execution_options(populate_existing=True)
    row = db.scalar(stmt)
    if row is None or row.digest != source.digest or (require_active and not row.active):
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The selected pack version is unavailable. Check the current pack version.")
    signer = db.get(NortPolePackSigner, row.signer_key_id, populate_existing=True)
    check = check_version(row, signer)
    if check.status != "verified" or check.signer_revoked:
        raise NortPoleError(NortPoleErrorCode.POLICY_BLOCKED, "The pack version must have a valid signature from a trusted signer.")
    manifest = Manifest.model_validate(row.manifest)
    agent = next((item for item in manifest.agents if item.id == source.agent_id and item.chat_pilot is not None), None)
    if agent is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "This signed pack agent is unavailable for Chat.")
    return manifest, agent


def _instructions(manifest: Manifest, agent: AgentSpec) -> str:
    guides = [
        f"{guide.name}\n{guide.body}"
        for guide in manifest.guides if guide.id in agent.guides
    ]
    return "\n\n".join([agent.instructions, *guides])


def validate_pack_chat_configuration(
    db: Session, draft: AgentPreviewDraft, *, require_active: bool = False,
) -> Manifest | None:
    if draft.pack_source is None:
        return None
    manifest, agent = pack_chat_definition(db, draft.pack_source, require_active=require_active)
    if (
        draft.pilot != agent.chat_pilot
        or draft.system_prompt != _instructions(manifest, agent)
        or draft.task_prompt
        or draft.replace_base_system_prompt
        or draft.datetime_aware
    ):
        raise NortPoleError(NortPoleErrorCode.INVALID_INPUT, "Use the instructions and read-only configuration defined by the signed pack.")
    return manifest


def stage_pack_chat_agent(
    db: Session, user: User, pack_id: str, version: str, agent_id: str,
) -> int:
    # Serialize retries and simultaneous staging for the same owner and agent.
    key = f"pack-chat-agent:{user.id}:{pack_id}:{agent_id}"
    db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))
    persona = db.scalar(select(Persona).where(
        Persona.user_id == user.id,
        Persona.chat_pack_id == pack_id,
        Persona.chat_pack_agent_id == agent_id,
    ).with_for_update())
    if persona is not None and persona.deleted:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "Restore the existing pack agent before preparing a new draft.")
    row = db.scalar(select(NortPolePackVersion).where(
        NortPolePackVersion.pack_id == pack_id,
        NortPolePackVersion.version == version,
    ))
    if row is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Pack version not found.")
    source = PackAgentSource(pack_id=pack_id, version=version, agent_id=agent_id, digest=row.digest)
    manifest, agent = pack_chat_definition(db, source, require_active=True)
    active = active_agent_release(db, persona.id) if persona is not None else None
    current = persona.agent_release_draft if persona is not None else None
    if current is None and active is not None:
        current = active.configuration
    if current is not None and current.pack_source == source:
        return persona.id

    name = current.name if current is not None else f"{agent.name} ({manifest.name})"[:200]
    draft = AgentPreviewDraft(
        name=name,
        system_prompt=_instructions(manifest, agent),
        pilot=agent.chat_pilot,
        pack_source=source,
        document_set_ids=current.document_set_ids if current is not None else [],
        model_configuration_id=current.model_configuration_id if current is not None else None,
        search_start_date=current.search_start_date if current is not None else None,
    )
    if persona is None:
        persona = Persona(
            user_id=user.id, name=name, description=agent.description,
            system_prompt=draft.system_prompt, is_public=False,
            chat_pack_id=pack_id, chat_pack_agent_id=agent_id,
        )
        db.add(persona)
    persona.agent_release_draft = draft
    db.flush()
    persona_id = persona.id
    db.commit()
    return persona_id
