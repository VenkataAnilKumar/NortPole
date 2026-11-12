"""Reading (data-access) groups of a source: EvolvXSI implementations of the
three functions the connector edit flow calls. Upstream kept them in its
enterprise edition; in the community copy they were silent no-ops, so an edit
that changed a source's reading groups saved nothing and reported success.
"""

from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from evolvxsi.db.document import mark_cc_pair_documents_for_sync__no_commit
from evolvxsi.db.enums import AccessType
from evolvxsi.db.models import (
    ConnectorCredentialPair,
    UserGroup,
    UserGroup__CCPairDataAccess,
)
from evolvxsi.db.user_group import assert_not_shared_with_default_group
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError


def fetch_data_access_groups_for_cc_pair(db_session: Session, cc_pair_id: int) -> list[UserGroup]:
    return list(
        db_session.scalars(
            select(UserGroup)
            .join(UserGroup__CCPairDataAccess, UserGroup__CCPairDataAccess.user_group_id == UserGroup.id)
            .where(UserGroup__CCPairDataAccess.cc_pair_id == cc_pair_id)
            .order_by(UserGroup.name)
        )
    )


def set_cc_pair_data_access_groups__no_commit(
    db_session: Session,
    *,
    cc_pair_id: int,
    requested_group_ids: Collection[int],
    visible_group_ids: set[int] | None,
) -> bool:
    """Sets the source's reading groups and returns whether they changed.

    `visible_group_ids` is the set of groups the editor can see (None: all).
    Groups the editor cannot see are kept as they are, so a scoped manager
    cannot remove a group they do not know about. When the groups change, the
    source's documents are marked for the metadata re-sync so their stored
    access lists follow.
    """
    requested = set(requested_group_ids)
    if visible_group_ids is not None and (outside := requested - visible_group_ids):
        raise EvolvXSIError(
            EvolvXSIErrorCode.INSUFFICIENT_PERMISSIONS,
            f"You cannot share with group(s) you cannot see: {sorted(outside)}",
        )
    assert_not_shared_with_default_group(db_session, requested)
    if requested:
        found = set(
            db_session.scalars(
                select(UserGroup.id).where(UserGroup.id.in_(requested), UserGroup.is_up_for_deletion.is_(False))
            )
        )
        if missing := requested - found:
            raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, f"User group(s) not found: {sorted(missing)}")

    cc_pair = db_session.scalar(select(ConnectorCredentialPair).where(ConnectorCredentialPair.id == cc_pair_id))
    if cc_pair is None:
        raise EvolvXSIError(EvolvXSIErrorCode.CONNECTOR_NOT_FOUND, f"Source {cc_pair_id} does not exist.")

    current = set(
        db_session.scalars(
            select(UserGroup__CCPairDataAccess.user_group_id).where(UserGroup__CCPairDataAccess.cc_pair_id == cc_pair_id)
        )
    )
    hidden_kept = current if visible_group_ids is None else current - visible_group_ids
    target = requested | (set() if visible_group_ids is None else hidden_kept)
    if target == current:
        return False
    if target and cc_pair.access_type not in AccessType.data_access_types():
        raise EvolvXSIError(
            EvolvXSIErrorCode.INVALID_INPUT, f"Access type {cc_pair.access_type} takes no reading groups."
        )
    db_session.execute(delete(UserGroup__CCPairDataAccess).where(UserGroup__CCPairDataAccess.cc_pair_id == cc_pair_id))
    for gid in target:
        db_session.add(
            UserGroup__CCPairDataAccess(cc_pair_id=cc_pair_id, user_group_id=gid, access_type=cc_pair.access_type)
        )
    db_session.flush()
    mark_cc_pair_documents_for_sync__no_commit(db_session, [cc_pair_id])
    return True


def assert_restricted_cc_pairs_keep_a_group(db_session: Session, cc_pair_ids: Collection[int]) -> None:
    """A permission-synced (SYNC_RESTRICTED) source with no reading group would
    be visible to nobody, so it must keep at least one."""
    for cc_pair_id in cc_pair_ids:
        cc_pair = db_session.scalar(select(ConnectorCredentialPair).where(ConnectorCredentialPair.id == cc_pair_id))
        if cc_pair is None or cc_pair.access_type != AccessType.SYNC_RESTRICTED:
            continue
        has_group = db_session.scalar(
            select(UserGroup__CCPairDataAccess.user_group_id)
            .where(UserGroup__CCPairDataAccess.cc_pair_id == cc_pair_id)
            .limit(1)
        )
        if has_group is None:
            raise EvolvXSIError(
                EvolvXSIErrorCode.INVALID_INPUT, "A restricted connector needs at least one data-access group."
            )
