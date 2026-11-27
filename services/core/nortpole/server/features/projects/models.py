from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from nortpole.db.enums import UserFileStatus
from nortpole.db.models import UserFile, UserProject
from nortpole.db.project_access import ProjectRole
from nortpole.db.projects import CategorizedFilesResult
from nortpole.file_store.models import ChatFileType
from nortpole.server.query_and_chat.chat_utils import mime_type_to_chat_file_type
from nortpole.server.query_and_chat.models import ChatSessionDetails


class UserFileSnapshot(BaseModel):
    id: UUID
    temp_id: str | None = None  # Client-side temporary ID for optimistic updates
    name: str
    project_id: int | None = None
    user_id: UUID | None
    file_id: str
    created_at: datetime
    status: UserFileStatus
    last_accessed_at: datetime | None
    file_type: str | None
    chat_file_type: ChatFileType
    token_count: int | None
    chunk_count: int | None

    @classmethod
    def from_model(
        cls, model: UserFile, temp_id_map: dict[str, str] | None = None
    ) -> "UserFileSnapshot":
        if temp_id_map is None:
            temp_id_map = {}
        return cls(
            id=model.id,
            temp_id=temp_id_map.get(str(model.id)),
            name=model.name,
            project_id=None,
            user_id=model.user_id,
            file_id=model.file_id,
            created_at=model.created_at,
            status=model.status,
            last_accessed_at=model.last_accessed_at,
            file_type=model.content_type,
            chat_file_type=mime_type_to_chat_file_type(model.content_type),
            token_count=model.token_count,
            chunk_count=model.chunk_count,
        )


class TokenCountResponse(BaseModel):
    total_tokens: int


class RejectedFile(BaseModel):
    file_name: str
    reason: str


class CategorizedFilesSnapshot(BaseModel):
    user_files: list[UserFileSnapshot]
    rejected_files: list[RejectedFile]

    @classmethod
    def from_result(cls, result: CategorizedFilesResult) -> "CategorizedFilesSnapshot":
        return cls(
            user_files=[
                UserFileSnapshot.from_model(user_file, temp_id_map=result.id_to_temp_id)
                for user_file in result.user_files
            ],
            rejected_files=[
                RejectedFile(
                    file_name=rejected_file.filename,
                    reason=rejected_file.reason,
                )
                for rejected_file in result.rejected_files
            ],
        )


class ProjectChatSnapshot(ChatSessionDetails):
    is_owned: bool


class UserProjectSnapshot(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    user_id: UUID | None
    instructions: str | None = None
    role: ProjectRole
    shared: bool
    chat_sessions: list[ProjectChatSnapshot]

    @classmethod
    def from_model(
        cls, model: UserProject, *, viewer_id: UUID | None = None,
        role: ProjectRole = "owner", shared: bool = False,
    ) -> "UserProjectSnapshot":
        return cls(
            id=model.id,
            name=model.name,
            description=model.description,
            created_at=model.created_at,
            user_id=model.user_id,
            instructions=model.instructions,
            role=role,
            shared=shared,
            # A project lists its sessions by title, so an incognito chat would
            # surface here the same way it would in the sidebar.
            chat_sessions=[
                ProjectChatSnapshot(
                    **ChatSessionDetails.from_model(chat).model_dump(),
                    is_owned=chat.user_id == (viewer_id or model.user_id),
                )
                for chat in model.chat_sessions
                if not chat.deleted and chat.incognito_record_mode is None
                and chat.spawned_by_message_id is None
            ],
        )


class ChatSessionRequest(BaseModel):
    chat_session_id: str
