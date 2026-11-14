"""Changing a source's reading groups through the core's own edit path
(`apply_access_change__no_commit`) on the real database.

Before NortPole filled them in, the functions this path calls were community
no-ops: the change saved nothing and reported success.
"""

import datetime
import uuid

import pytest

from evolvxsi.connectors.edit_plan.state import fetch_current_pair_state  # noqa: F401 (import check)
from evolvxsi.db.connector_edit_requests import apply_access_change__no_commit
from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.enums import AccessType
from evolvxsi.db.models import (
    Connector,
    ConnectorCredentialPair,
    Credential,
    Document,
    DocumentByConnectorCredentialPair,
    UserGroup,
    UserGroup__CCPairDataAccess,
)
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.knowledge.knowledge_access.source_groups import fetch_data_access_groups_for_cc_pair
from tests.evolvxsi_integration.test_group_access import _doc, _source, _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres and OpenSearch")

RUN = uuid.uuid4().hex[:8]
DOC = f"edit-doc-{RUN}"


@pytest.fixture(scope="module")
def world():  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        groups = {n: UserGroup(name=f"edit-{n}-{RUN}", is_up_to_date=True) for n in ("a", "b", "hidden")}
        s.add_all(groups.values())
        s.flush()
        c, cr, cc = _source(s, f"edit{RUN}", AccessType.PRIVATE)
        s.add_all([
            UserGroup__CCPairDataAccess(cc_pair_id=cc.id, user_group_id=groups["a"].id, access_type=AccessType.PRIVATE),
            UserGroup__CCPairDataAccess(cc_pair_id=cc.id, user_group_id=groups["hidden"].id, access_type=AccessType.PRIVATE),
        ])
        _doc(s, DOC, c, cr)
        s.query(Document).filter_by(id=DOC).update({"chunk_count": 1, "last_modified": datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc), "last_synced": datetime.datetime(2020, 1, 2, tzinfo=datetime.timezone.utc)})
        s.commit()
        ids = {"g": {k: g.id for k, g in groups.items()}, "cc": cc.id, "c": c.id, "cr": cr.id}
    yield ids
    with get_session_with_current_tenant() as s:
        s.query(DocumentByConnectorCredentialPair).filter_by(id=DOC).delete()
        s.query(Document).filter_by(id=DOC).delete()
        s.query(UserGroup__CCPairDataAccess).filter_by(cc_pair_id=ids["cc"]).delete()
        s.query(ConnectorCredentialPair).filter_by(id=ids["cc"]).delete()
        s.query(Credential).filter_by(id=ids["cr"]).delete()
        s.query(Connector).filter_by(id=ids["c"]).delete()
        s.query(UserGroup).filter(UserGroup.id.in_(list(ids["g"].values()))).delete()
        s.commit()


def _groups(cc_id: int) -> set[int]:
    with get_session_with_current_tenant() as s:
        return {g.id for g in fetch_data_access_groups_for_cc_pair(s, cc_id)}


def _dirty() -> bool:
    with get_session_with_current_tenant() as s:
        d = s.get(Document, DOC)
        return d.last_modified > d.last_synced


def test_edit_reads_the_real_current_groups(world) -> None:  # type: ignore[no-untyped-def]
    assert _groups(world["cc"]) == {world["g"]["a"], world["g"]["hidden"]}


def test_scoped_editor_changes_only_groups_they_can_see(world) -> None:  # type: ignore[no-untyped-def]
    g = world["g"]
    with get_session_with_current_tenant() as s:
        apply_access_change__no_commit(s, world["cc"], AccessType.PRIVATE, {g["b"]}, visible_group_ids={g["a"], g["b"]})
        s.commit()
    # a replaced by b; the group the editor cannot see is kept.
    assert _groups(world["cc"]) == {g["b"], g["hidden"]}
    assert _dirty(), "documents must be marked for the access re-sync"


def test_cannot_add_a_group_the_editor_cannot_see(world) -> None:  # type: ignore[no-untyped-def]
    g = world["g"]
    with get_session_with_current_tenant() as s, pytest.raises(EvolvXSIError):
        apply_access_change__no_commit(s, world["cc"], AccessType.PRIVATE, {g["hidden"]}, visible_group_ids={g["a"], g["b"]})


def test_restricted_source_needs_a_group(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        with pytest.raises(EvolvXSIError):
            apply_access_change__no_commit(s, world["cc"], AccessType.SYNC_RESTRICTED, set(), visible_group_ids=None)
        s.rollback()
    assert world["g"]["b"] in _groups(world["cc"]), "a refused change leaves the groups as they were"


def test_making_the_source_public_removes_its_groups(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        apply_access_change__no_commit(s, world["cc"], AccessType.PUBLIC, set(), visible_group_ids=None)
        s.commit()
    assert _groups(world["cc"]) == set()
