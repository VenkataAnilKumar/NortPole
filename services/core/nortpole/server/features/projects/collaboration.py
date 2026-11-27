"""Project access management and project-scoped reads."""

from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, lazyload
from starlette.responses import StreamingResponse

from nortpole.auth.permissions import require_permission
from nortpole.configs.constants import MessageType
from nortpole.db.chat import get_chat_message_page_ids
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import ChatSessionSharedStatus, Permission, UserFileStatus
from nortpole.db.models import ChatMessage, ChatSession, Project__UserFile, ProjectMember, User, UserFile
from nortpole.db.project_access import MemberRole, require_project
from nortpole.file_store.file_store import get_default_file_store

router = APIRouter()
NO_STORE = {"Cache-Control": "private, no-store", "Vary": "Cookie"}


class MemberRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    role: MemberRole


class RoleRequest(BaseModel):
    role: MemberRole


class MemberSnapshot(BaseModel):
    user_id: UUID
    email: str
    name: str | None
    role: MemberRole


def _member_snapshot(user: User, membership: ProjectMember) -> MemberSnapshot:
    return MemberSnapshot.model_validate(
        dict(user_id=user.id, email=user.email, name=user.personal_name, role=membership.role)
    )


@router.get("/{project_id}/members")
def list_members(
    project_id: int,
    response: Response,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> list[MemberSnapshot]:
    require_project(project_id, user.id, db, minimum="owner")
    response.headers.update(NO_STORE)
    return [
        _member_snapshot(member_user, membership)
        for member_user, membership in db.execute(
            select(User, ProjectMember)
            .options(lazyload("*"))
            .join(ProjectMember, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project_id)
            .order_by(User.email)
        )
    ]


@router.post("/{project_id}/members")
def add_member(
    project_id: int,
    body: MemberRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> MemberSnapshot:
    require_project(project_id, user.id, db, minimum="owner", lock=True)
    if db.scalar(
        select(ChatSession.id).where(
            ChatSession.project_id == project_id,
            ChatSession.shared_status == ChatSessionSharedStatus.PUBLIC,
            ChatSession.deleted.is_(False),
        ).limit(1)
    ) is not None:
        raise HTTPException(409, "Turn off public sharing for this project's chats before adding people.")
    recipients = db.scalars(
        select(User).options(lazyload("*")).where(
            func.lower(User.email) == body.email.strip().lower(),
            User.is_active.is_(True),
        ).order_by(User.id).limit(2)
    ).all()
    if len(recipients) != 1:
        raise HTTPException(404, "No active workspace account matches this email.")
    recipient = recipients[0]
    if recipient.id == user.id:
        raise HTTPException(409, "You already own this project.")
    membership = db.get(ProjectMember, (project_id, recipient.id))
    if membership is None:
        membership = ProjectMember(project_id=project_id, user_id=recipient.id, role=body.role)
        db.add(membership)
    elif membership.role != body.role:
        raise HTTPException(409, "This person already has access. Change their role in the member list.")
    snapshot = _member_snapshot(recipient, membership)
    db.commit()
    return snapshot


def _detach_chats(project_id: int, member_id: UUID, db: Session) -> None:
    db.execute(
        update(ChatSession)
        .where(ChatSession.project_id == project_id, ChatSession.user_id == member_id)
        .values(project_id=None)
    )


@router.patch("/{project_id}/members/{member_id}")
def change_member_role(
    project_id: int,
    member_id: UUID,
    body: RoleRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> MemberSnapshot:
    require_project(project_id, user.id, db, minimum="owner", lock=True)
    membership = db.get(ProjectMember, (project_id, member_id), populate_existing=True)
    recipient = db.get(User, member_id)
    if membership is None or recipient is None:
        raise HTTPException(404, "Project member not found")
    if membership.role == "editor" and body.role == "viewer":
        _detach_chats(project_id, member_id, db)
    membership.role = body.role
    snapshot = _member_snapshot(recipient, membership)
    db.commit()
    return snapshot


@router.delete("/{project_id}/members/{member_id}", status_code=204)
def remove_member(
    project_id: int,
    member_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> Response:
    require_project(project_id, user.id, db, minimum="owner", lock=True)
    membership = db.get(ProjectMember, (project_id, member_id), populate_existing=True)
    if membership is not None:
        _detach_chats(project_id, member_id, db)
        db.delete(membership)
    db.commit()
    return Response(status_code=204)


class TranscriptMessage(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    text: str


class ProjectTranscript(BaseModel):
    title: str | None
    messages: list[TranscriptMessage]
    has_older: bool


@router.get("/{project_id}/chats/{chat_id}")
def get_project_transcript(
    project_id: int,
    chat_id: UUID,
    response: Response,
    before: Annotated[int | None, Query(gt=0)] = None,
    user: User = Depends(require_permission(Permission.READ_CHAT)),
    db: Session = Depends(get_session),
) -> ProjectTranscript:
    require_project(project_id, user.id, db)
    chat = db.scalar(
        select(ChatSession).where(
            ChatSession.id == chat_id,
            ChatSession.project_id == project_id,
            ChatSession.spawned_by_message_id.is_(None),
            ChatSession.incognito_record_mode.is_(None),
            ChatSession.deleted.is_(False),
        )
    )
    if chat is None:
        raise HTTPException(404, "Project chat not found")
    page, has_older = get_chat_message_page_ids(
        chat_session_id=chat_id, db_session=db, limit=50, before_message_id=before, include_siblings=False
    )
    rows = db.execute(
        select(ChatMessage.id, ChatMessage.message_type, ChatMessage.message)
        .where(
            ChatMessage.chat_session_id == chat_id,
            ChatMessage.id.in_(page),
            ChatMessage.message_type.in_((MessageType.USER, MessageType.ASSISTANT)),
        )
        .order_by(ChatMessage.id)
    )
    response.headers.update(NO_STORE)
    return ProjectTranscript(
        title=chat.description,
        messages=[
            TranscriptMessage(id=message_id, role="user" if kind == MessageType.USER else "assistant", text=text)
            for message_id, kind, text in rows
        ],
        has_older=has_older,
    )


@router.get("/{project_id}/files/{file_id}/download")
def download_project_file(
    project_id: int,
    file_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> Response:
    require_project(project_id, user.id, db)
    item = db.scalar(
        select(UserFile).join(Project__UserFile).where(
            Project__UserFile.project_id == project_id,
            UserFile.id == file_id,
            UserFile.incognito.is_(False),
            UserFile.status.notin_((UserFileStatus.FAILED, UserFileStatus.DELETING)),
        )
    )
    if item is None:
        raise HTTPException(404, "Project file not found")
    store = get_default_file_store()
    if not store.read_file_record(item.file_id):
        raise HTTPException(404, "Project file not found")
    return StreamingResponse(
        store.read_file(item.file_id, mode="b"),
        media_type="application/octet-stream",
        headers={
            **NO_STORE,
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(item.name, safe='')}",
            "X-Content-Type-Options": "nosniff",
        },
    )
