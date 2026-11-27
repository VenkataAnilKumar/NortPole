"""Access policy for explicitly shared workspace projects."""

from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import exists, select
from sqlalchemy.orm import Session, lazyload

from nortpole.db.models import ProjectMember, UserProject

MemberRole = Literal["viewer", "editor"]
ProjectRole = Literal["owner", "viewer", "editor"]


def project_has_members(project_id: int, db: Session) -> bool:
    return bool(db.scalar(select(exists().where(ProjectMember.project_id == project_id))))


def project_role(project: UserProject, user_id: UUID | None, db: Session) -> ProjectRole | None:
    if user_id is None:
        return None
    if project.user_id == user_id:
        return "owner"
    member = db.get(ProjectMember, (project.id, user_id), populate_existing=True)
    if member is not None:
        return "editor" if member.role == "editor" else "viewer"
    return None


def require_project(
    project_id: int,
    user_id: UUID | None,
    db: Session,
    *,
    minimum: ProjectRole = "viewer",
    lock: bool = False,
) -> tuple[UserProject, ProjectRole]:
    stmt = select(UserProject).options(lazyload(UserProject.chat_sessions)).where(UserProject.id == project_id)
    if lock:
        stmt = stmt.with_for_update()
    project = db.scalar(stmt)
    role = project_role(project, user_id, db) if project is not None else None
    if project is None or role is None:
        raise HTTPException(404, "Project not found")
    allowed = {
        "viewer": ("viewer", "editor", "owner"),
        "editor": ("editor", "owner"),
        "owner": ("owner",),
    }
    if role not in allowed[minimum]:
        raise HTTPException(403, "Your project role does not allow this action")
    return project, role
