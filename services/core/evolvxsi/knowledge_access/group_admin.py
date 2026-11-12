"""Create and maintain access groups (EvolvXSI-owned; upstream kept this in its
enterprise edition).

A group's name is what documents carry on their access lists (`group:<name>`),
so two changes are refused while a group is a reading group of any source:
renaming it and deleting it. Either would leave stored access lists naming a
group that no longer exists under that name, and a new group given the old name
would silently inherit the access. Remove the group from its sources first.

The built-in role groups are not managed here; membership of those decides
roles and has its own screens.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import (
    ConnectorCredentialPair,
    User,
    User__UserGroup,
    UserGroup,
    UserGroup__CCPairDataAccess,
)
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.route_policy.audit import record_audit
from evolvxsi.utils.audit import AuditAction, AuditOutcome

router = APIRouter(prefix="/admin/access-groups")

MAX_NAME = 80


class Member(BaseModel):
    id: UUID
    email: str


class SourceRef(BaseModel):
    cc_pair_id: int
    name: str | None


class GroupView(BaseModel):
    id: int
    name: str
    is_default: bool
    members: list[Member]
    # Sources this group may read. Changed from each source's own settings.
    sources: list[SourceRef]


class GroupCreate(BaseModel):
    name: str
    user_ids: list[UUID] = []

    @field_validator("name")
    @classmethod
    def _clean(cls, v: str) -> str:
        return clean_name(v)


class GroupUpdate(BaseModel):
    name: str | None = None
    user_ids: list[UUID] | None = None

    @field_validator("name")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        return None if v is None else clean_name(v)


def clean_name(name: str) -> str:
    name = " ".join(name.split())
    if not name:
        raise ValueError("A group needs a name.")
    if len(name) > MAX_NAME:
        raise ValueError(f"A group name can be at most {MAX_NAME} characters.")
    return name


def _view(db: Session, group: UserGroup) -> GroupView:
    members = db.execute(
        select(User.id, User.email)
        .join(User__UserGroup, User__UserGroup.user_id == User.id)
        .where(User__UserGroup.user_group_id == group.id)
        .order_by(User.email)
    ).tuples()
    sources = db.execute(
        select(ConnectorCredentialPair.id, ConnectorCredentialPair.name)
        .join(
            UserGroup__CCPairDataAccess,
            UserGroup__CCPairDataAccess.cc_pair_id == ConnectorCredentialPair.id,
        )
        .where(UserGroup__CCPairDataAccess.user_group_id == group.id)
        .order_by(ConnectorCredentialPair.name)
    ).tuples()
    return GroupView(
        id=group.id,
        name=group.name,
        is_default=group.is_default,
        members=[Member(id=i, email=e) for i, e in members],
        sources=[SourceRef(cc_pair_id=i, name=n) for i, n in sources],
    )


def _get(db: Session, group_id: int) -> UserGroup:
    group = db.get(UserGroup, group_id)
    if group is None or group.is_up_for_deletion:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Group not found.")
    return group


def _refuse_default(group: UserGroup) -> None:
    if group.is_default:
        raise EvolvXSIError(
            EvolvXSIErrorCode.CONFLICT,
            "Built-in role groups are not managed here.",
        )


def _source_count(db: Session, group_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(UserGroup__CCPairDataAccess)
            .where(UserGroup__CCPairDataAccess.user_group_id == group_id)
        )
        or 0
    )


def _refuse_name_in_use(db: Session, name: str, except_id: int | None = None) -> None:
    stmt = select(UserGroup.id).where(func.lower(UserGroup.name) == name.lower())
    if except_id is not None:
        stmt = stmt.where(UserGroup.id != except_id)
    if db.scalar(stmt.limit(1)) is not None:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "A group with that name already exists.")


def _set_members(db: Session, group_id: int, user_ids: list[UUID]) -> None:
    wanted = set(user_ids)
    if wanted:
        found = set(db.scalars(select(User.id).where(User.id.in_(wanted))))
        if missing := wanted - found:
            raise EvolvXSIError(
                EvolvXSIErrorCode.INVALID_INPUT, f"{len(missing)} selected user(s) do not exist."
            )
    db.execute(delete(User__UserGroup).where(User__UserGroup.user_group_id == group_id))
    for uid in wanted:
        db.add(User__UserGroup(user_id=uid, user_group_id=group_id))


@router.get("")
def list_groups(
    _: User = Depends(require_permission(Permission.MANAGE_USER_GROUPS)),
    db_session: Session = Depends(get_session),
) -> list[GroupView]:
    groups = db_session.scalars(
        select(UserGroup).where(UserGroup.is_up_for_deletion.is_(False)).order_by(UserGroup.name)
    )
    return [_view(db_session, g) for g in groups]


@router.post("")
def create_group(
    body: GroupCreate,
    user: User = Depends(require_permission(Permission.MANAGE_USER_GROUPS)),
    db_session: Session = Depends(get_session),
) -> GroupView:
    _refuse_name_in_use(db_session, body.name)
    # No stored access list names a new group, so it is in step from the start.
    group = UserGroup(name=body.name, is_up_to_date=True)
    db_session.add(group)
    db_session.flush()
    _set_members(db_session, group.id, body.user_ids)
    db_session.commit()
    record_audit(
        AuditAction.USER_GROUP_CREATE,
        AuditOutcome.SUCCESS,
        actor=user,
        summary=f"Created group {group.name} with {len(set(body.user_ids))} member(s)",
        resource_type="user_group",
        resource_id=group.id,
    )
    return _view(db_session, group)


@router.patch("/{group_id}")
def update_group(
    group_id: int,
    body: GroupUpdate,
    user: User = Depends(require_permission(Permission.MANAGE_USER_GROUPS)),
    db_session: Session = Depends(get_session),
) -> GroupView:
    group = _get(db_session, group_id)
    _refuse_default(group)
    changes: list[str] = []
    if body.name is not None and body.name != group.name:
        if _source_count(db_session, group_id) > 0:
            raise EvolvXSIError(
                EvolvXSIErrorCode.CONFLICT,
                "This group can read one or more sources. Remove it from those sources before renaming it.",
            )
        _refuse_name_in_use(db_session, body.name, except_id=group_id)
        changes.append(f"renamed from {group.name} to {body.name}")
        group.name = body.name
    if body.user_ids is not None:
        _set_members(db_session, group_id, body.user_ids)
        changes.append(f"members set to {len(set(body.user_ids))}")
    db_session.commit()
    if changes:
        record_audit(
            AuditAction.USER_GROUP_CHANGE,
            AuditOutcome.SUCCESS,
            actor=user,
            summary=f"Group {group.name}: " + "; ".join(changes),
            resource_type="user_group",
            resource_id=group.id,
        )
    return _view(db_session, group)


@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    user: User = Depends(require_permission(Permission.MANAGE_USER_GROUPS)),
    db_session: Session = Depends(get_session),
) -> None:
    group = _get(db_session, group_id)
    _refuse_default(group)
    if _source_count(db_session, group_id) > 0:
        raise EvolvXSIError(
            EvolvXSIErrorCode.CONFLICT,
            "This group can read one or more sources. Remove it from those sources before deleting it.",
        )
    name = group.name
    db_session.execute(delete(User__UserGroup).where(User__UserGroup.user_group_id == group_id))
    db_session.delete(group)
    db_session.commit()
    record_audit(
        AuditAction.USER_GROUP_DELETE,
        AuditOutcome.SUCCESS,
        actor=user,
        summary=f"Deleted group {name}",
        resource_type="user_group",
        resource_id=group_id,
    )
