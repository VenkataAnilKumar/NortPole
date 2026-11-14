"""NortPole group access (replaces the community stubs, which have no groups).

Two sides must agree for a group to grant access:

* the person: every group they belong to is on their access list as
  `group:<name>` (see `group_names_for_user`);
* the document: every data-access group of a PRIVATE source the document came
  from is on the document's access list (see `group_names_for_documents`).

Only data-access links grant reading (`UserGroup__CCPairDataAccess`). The other
link table, `UserGroup__ConnectorCredentialPair`, says who may manage a source
and grants no reading. A SYNC_RESTRICTED source lets group members see only
what the source's own permissions allow; a group entry alone cannot express
that, so those sources grant nothing through groups here (fail closed) until a
per-source permission sync exists.

Removing a person from a group takes effect on their next search, because their
access list is built per request. Removing a group from a source changes stored
document access lists only when those documents are written to the index
again; until a re-sync step exists, that change needs a re-index of the source.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from nortpole.db.enums import AccessType
from nortpole.db.models import (
    ConnectorCredentialPair,
    DocumentByConnectorCredentialPair,
    User__UserGroup,
    UserGroup,
    UserGroup__CCPairDataAccess,
)


def group_names_for_user(db_session: Session, user_id: UUID) -> set[str]:
    rows = db_session.scalars(
        select(UserGroup.name)
        .join(User__UserGroup, User__UserGroup.user_group_id == UserGroup.id)
        .where(User__UserGroup.user_id == user_id)
        .where(UserGroup.is_up_for_deletion.is_(False))
    )
    return set(rows)


def group_names_for_documents(
    db_session: Session, document_ids: list[str]
) -> dict[str, set[str]]:
    """Data-access groups of the PRIVATE sources each document came from."""
    if not document_ids:
        return {}
    rows = db_session.execute(
        select(DocumentByConnectorCredentialPair.id, UserGroup.name)
        .join(
            ConnectorCredentialPair,
            and_(
                ConnectorCredentialPair.connector_id
                == DocumentByConnectorCredentialPair.connector_id,
                ConnectorCredentialPair.credential_id
                == DocumentByConnectorCredentialPair.credential_id,
            ),
        )
        .join(
            UserGroup__CCPairDataAccess,
            UserGroup__CCPairDataAccess.cc_pair_id == ConnectorCredentialPair.id,
        )
        .join(UserGroup, UserGroup.id == UserGroup__CCPairDataAccess.user_group_id)
        .where(DocumentByConnectorCredentialPair.id.in_(document_ids))
        .where(ConnectorCredentialPair.access_type == AccessType.PRIVATE)
        .where(UserGroup.is_up_for_deletion.is_(False))
    ).tuples()
    out: dict[str, set[str]] = defaultdict(set)
    for doc_id, name in rows:
        out[doc_id].add(name)
    return dict(out)


def user_group_cc_pair_clause(user_id: UUID) -> ColumnElement[bool]:
    """True for a source with a data-access group the user belongs to. The
    caller already limits this to sources that are not permission-synced."""
    return exists(
        select(1)
        .select_from(UserGroup__CCPairDataAccess)
        .join(
            User__UserGroup,
            User__UserGroup.user_group_id == UserGroup__CCPairDataAccess.user_group_id,
        )
        .join(UserGroup, UserGroup.id == UserGroup__CCPairDataAccess.user_group_id)
        .where(
            UserGroup__CCPairDataAccess.cc_pair_id == ConnectorCredentialPair.id,
            User__UserGroup.user_id == user_id,
            UserGroup.is_up_for_deletion.is_(False),
        )
        .correlate(ConnectorCredentialPair)
    )
