from sqlalchemy import select
from sqlalchemy.orm import Session

from nortpole.db.models import AgentRelease, Persona


def active_agent_release(db: Session, persona_id: int) -> AgentRelease | None:
    return db.scalar(select(AgentRelease).where(
        AgentRelease.persona_id == persona_id, AgentRelease.is_active.is_(True)
    ))


def lock_agent_release_state(db: Session, persona_id: int, *, read: bool = False) -> None:
    # This also serializes candidates for agents that have no version yet.
    db.execute(select(Persona.id).where(Persona.id == persona_id).with_for_update(read=read))
