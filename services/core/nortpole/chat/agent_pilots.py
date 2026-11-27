from pydantic import BaseModel
from sqlalchemy.orm import Session

from nortpole.db.agent_preview import AgentPreview
from nortpole.db.agent_preview import AgentPilotKind
from nortpole.db.document_set import get_document_set_by_id_for_user
from nortpole.db.models import User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.query_and_chat.models import SearchEvidenceSelection


class PilotLibrary(BaseModel):
    id: int
    name: str


class AgentPilotInput(BaseModel):
    kind: AgentPilotKind
    libraries: list[PilotLibrary]


def describe_pilot(configuration: AgentPreview, user: User, db: Session) -> AgentPilotInput | None:
    if configuration.pilot is None:
        return None
    return AgentPilotInput(
        kind=configuration.pilot,
        libraries=[
            PilotLibrary(id=library.id, name=library.name)
            for library_id in configuration.document_set_ids
            if (library := get_document_set_by_id_for_user(db, library_id, user, get_editable=False)) is not None
        ],
    )


def pilot_document_selection(
    configuration: AgentPreview, selection: SearchEvidenceSelection | None
) -> SearchEvidenceSelection | None:
    if configuration.pilot != "document-analysis":
        return None
    if selection is None or not selection.documents or selection.library_id is not None:
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT,
            "Select one to five documents from this agent’s Knowledge libraries before sending.",
        )
    return selection
