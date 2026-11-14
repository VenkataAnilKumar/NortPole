"""Create and maintain access groups (NortPole-owned; upstream kept this in its
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
from evolvxsi.db.enums import AccessType, Permission
from evolvxsi.db.models import (
    ConnectorCredentialPair,
    Document,
    DocumentByConnectorCredentialPair,
    User,
    User__UserGroup,
    UserGroup,
    UserGroup__CCPairDataAccess,
)
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.knowledge.knowledge_access.source_groups import (
    assert_restricted_cc_pairs_keep_a_group,
    fetch_data_access_groups_for_cc_pair,
    set_cc_pair_data_access_groups__no_commit,
)
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.governance.route_policy.audit import record_audit
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


class SourceGroupsUpdate(BaseModel):
    group_ids: list[int]


class SourceGroupsView(BaseModel):
    cc_pair_id: int
    group_ids: list[int]
    # Documents marked for a metadata re-sync, so their stored access lists
    # catch up with the change.
    documents_marked_for_resync: int


def _count_marked_documents(db: Session, cc_pair: ConnectorCredentialPair) -> int:
    """Indexed documents of this source (the ones the re-sync rewrites)."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(Document)
            .join(DocumentByConnectorCredentialPair, DocumentByConnectorCredentialPair.id == Document.id)
            .where(
                DocumentByConnectorCredentialPair.connector_id == cc_pair.connector_id,
                DocumentByConnectorCredentialPair.credential_id == cc_pair.credential_id,
                Document.chunk_count.is_not(None),
            )
        )
        or 0
    )


@router.put("/sources/{cc_pair_id}")
def set_source_groups(
    cc_pair_id: int,
    body: SourceGroupsUpdate,
    user: User = Depends(require_permission(Permission.MANAGE_USER_GROUPS)),
    db_session: Session = Depends(get_session),
) -> SourceGroupsView:
    """Replace the groups that may read a source.

    Uses the same rules as the connector edit form (`source_groups`): only
    private and permission-synced sources take groups, a permission-synced
    source keeps at least one, built-in and unknown groups are refused, and a
    change marks the source's documents for the access re-sync.
    """
    cc_pair = db_session.scalar(
        select(ConnectorCredentialPair).where(ConnectorCredentialPair.id == cc_pair_id)
    )
    if cc_pair is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Source not found.")
    if cc_pair.access_type not in (AccessType.PRIVATE, AccessType.SYNC_RESTRICTED):
        raise EvolvXSIError(
            EvolvXSIErrorCode.INVALID_INPUT,
            "Only private and permission-synced sources take reading groups.",
        )
    wanted = set(body.group_ids)
    before = {g.id for g in fetch_data_access_groups_for_cc_pair(db_session, cc_pair_id)}
    changed = set_cc_pair_data_access_groups__no_commit(
        db_session, cc_pair_id=cc_pair_id, requested_group_ids=wanted, visible_group_ids=None
    )
    assert_restricted_cc_pairs_keep_a_group(db_session, [cc_pair_id])
    marked = _count_marked_documents(db_session, cc_pair) if changed else 0
    db_session.commit()
    if changed:
        record_audit(
            AuditAction.USER_GROUP_CHANGE,
            AuditOutcome.SUCCESS,
            actor=user,
            summary=(
                f"Reading groups of source {cc_pair.name or cc_pair_id} changed: "
                f"added {sorted(wanted - before)}, removed {sorted(before - wanted)}; "
                f"{marked} document(s) marked for re-sync"
            ),
            resource_type="cc_pair",
            resource_id=cc_pair_id,
        )
    return SourceGroupsView(
        cc_pair_id=cc_pair_id, group_ids=sorted(wanted), documents_marked_for_resync=marked
    )
