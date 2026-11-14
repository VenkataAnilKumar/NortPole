"""Group access end to end on the real database and a real OpenSearch (A5).

A document from a PRIVATE source whose data-access group is "research" must be
found by a group member and not by anyone else, and must stop being found the
moment the member is removed from the group. A group that only manages a
source, and a data-access group on a SYNC_RESTRICTED source, grant no reading. Uses the core's own access functions and
retrieval. Skips when Postgres or OpenSearch is not running.

Rows are created with unique names and removed afterwards.
"""

import os
import uuid

import pytest
import requests

from types import SimpleNamespace

from nortpole.access.access import _get_acl_for_user, get_access_for_document, get_access_for_documents
from nortpole.configs.constants import DocumentSource
from nortpole.context.search.models import IndexFilters
from nortpole.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant
from nortpole.db.enums import (
    AccessType,
    ConnectorCredentialPairStatus,
    ConnectorManageRole,
    VectorQuantization,
)
from nortpole.db.models import (
    Connector,
    ConnectorCredentialPair,
    Credential,
    Document,
    DocumentByConnectorCredentialPair,
    User,
    User__UserGroup,
    UserGroup,
    UserGroup__CCPairDataAccess,
    UserGroup__ConnectorCredentialPair,
)
from nortpole.document_index.interfaces import IndexingMetadata, MetadataUpdateRequest, TenantState
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.knowledge.knowledge_access.group_admin import SourceGroupsUpdate, set_source_groups
from nortpole.document_index.opensearch.opensearch_document_index import (
    OpenSearchDocumentIndex,
)
from tests.nortpole_integration.test_retrieval_acl import DIM, TENANT, _chunk, _vector


def _up() -> bool:
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    try:
        if not requests.get(f"http://{host}:9200", timeout=2).ok:
            return False
        SqlEngine.init_engine(pool_size=2, max_overflow=0)
        with get_session_with_current_tenant() as s:
            s.execute(__import__("sqlalchemy").text("select 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres and OpenSearch")

RUN = uuid.uuid4().hex[:8]
DOC_ID = f"grp-doc-{RUN}"
SYNC_DOC_ID = f"grp-sync-doc-{RUN}"


def _source(s, tag: str, access_type: AccessType):  # type: ignore[no-untyped-def]
    connector = Connector(name=f"c-{tag}-{RUN}", source=DocumentSource.FILE, connector_specific_config={})
    credential = Credential(name=f"cr-{tag}-{RUN}", source=DocumentSource.FILE, credential_json={})
    s.add_all([connector, credential])
    s.flush()
    cc = ConnectorCredentialPair(
        name=f"cc-{tag}-{RUN}",
        connector_id=connector.id,
        credential_id=credential.id,
        status=ConnectorCredentialPairStatus.ACTIVE,
        access_type=access_type,
    )
    s.add(cc)
    s.flush()
    return connector, credential, cc


def _doc(s, doc_id: str, connector, credential) -> None:  # type: ignore[no-untyped-def]
    s.add(Document(id=doc_id, semantic_id=doc_id, from_ingestion_api=False, chunk_count=1))
    s.flush()
    s.add(DocumentByConnectorCredentialPair(id=doc_id, connector_id=connector.id, credential_id=credential.id, has_been_indexed=True))


@pytest.fixture(scope="module")
def world():  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        users = {
            n: User(id=uuid.uuid4(), email=f"{n}-{RUN}@example.com", hashed_password="x", is_active=True, is_verified=True)
            for n in ("member", "outsider", "manager", "syncmember")
        }
        groups = {n: UserGroup(name=f"{n}-{RUN}", is_up_to_date=True) for n in ("research", "managers", "syncgroup")}
        s.add_all([*users.values(), *groups.values()])
        s.flush()
        c1, cr1, private_cc = _source(s, "private", AccessType.PRIVATE)
        c2, cr2, sync_cc = _source(s, "sync", AccessType.SYNC_RESTRICTED)
        s.add_all([
            User__UserGroup(user_id=users["member"].id, user_group_id=groups["research"].id),
            User__UserGroup(user_id=users["manager"].id, user_group_id=groups["managers"].id),
            User__UserGroup(user_id=users["syncmember"].id, user_group_id=groups["syncgroup"].id),
            UserGroup__CCPairDataAccess(cc_pair_id=private_cc.id, user_group_id=groups["research"].id, access_type=AccessType.PRIVATE),
            UserGroup__ConnectorCredentialPair(cc_pair_id=private_cc.id, user_group_id=groups["managers"].id, is_current=True, role=ConnectorManageRole.EDITOR),
            UserGroup__CCPairDataAccess(cc_pair_id=sync_cc.id, user_group_id=groups["syncgroup"].id, access_type=AccessType.SYNC_RESTRICTED),
        ])
        s.flush()
        _doc(s, DOC_ID, c1, cr1)
        _doc(s, SYNC_DOC_ID, c2, cr2)
        s.commit()
        ids = {**{k: u.id for k, u in users.items()}, "groups": [g.id for g in groups.values()],
               "research": groups["research"].id, "managers": groups["managers"].id,
               "ccs": [private_cc.id, sync_cc.id], "connectors": [c1.id, c2.id], "credentials": [cr1.id, cr2.id]}

    with get_session_with_current_tenant() as s:
        access = get_access_for_documents([DOC_ID, SYNC_DOC_ID], s)
    name = f"evolvxsi_grp_test_{RUN}"
    idx = OpenSearchDocumentIndex(
        tenant_state=TenantState(tenant_id=TENANT, multitenant=False),
        index_name=name, embedding_dim=DIM, vector_quantization=VectorQuantization.NONE,
    )
    idx.verify_and_create_index_if_necessary(embedding_dim=DIM)
    chunks = []
    for doc_id in (DOC_ID, SYNC_DOC_ID):
        c = _chunk({"doc_id": doc_id, "title": doc_id, "text": f"research findings {doc_id}", "access": None})
        chunks.append(c.model_copy(update={"access": access[doc_id]}))
    idx.index(chunks, IndexingMetadata(doc_id_to_chunk_cnt_diff={d: IndexingMetadata.ChunkCounts(old_chunk_cnt=0, new_chunk_cnt=1) for d in (DOC_ID, SYNC_DOC_ID)}))
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    requests.post(f"http://{host}:9200/{name}/_refresh", timeout=10)
    yield ids, access, idx

    requests.delete(f"http://{host}:9200/{name}", timeout=10)
    with get_session_with_current_tenant() as s:
        s.query(DocumentByConnectorCredentialPair).filter(DocumentByConnectorCredentialPair.id.in_([DOC_ID, SYNC_DOC_ID])).delete()
        s.query(Document).filter(Document.id.in_([DOC_ID, SYNC_DOC_ID])).delete()
        s.query(UserGroup__CCPairDataAccess).filter(UserGroup__CCPairDataAccess.cc_pair_id.in_(ids["ccs"])).delete()
        s.query(UserGroup__ConnectorCredentialPair).filter(UserGroup__ConnectorCredentialPair.cc_pair_id.in_(ids["ccs"])).delete()
        s.query(User__UserGroup).filter(User__UserGroup.user_group_id.in_(ids["groups"])).delete()
        s.query(ConnectorCredentialPair).filter(ConnectorCredentialPair.id.in_(ids["ccs"])).delete()
        s.query(Credential).filter(Credential.id.in_(ids["credentials"])).delete()
        s.query(Connector).filter(Connector.id.in_(ids["connectors"])).delete()
        s.query(UserGroup).filter(UserGroup.id.in_(ids["groups"])).delete()
        s.query(User).filter(User.id.in_([ids[k] for k in ("member", "outsider", "manager", "syncmember")])).delete()
        s.execute(__import__("sqlalchemy").text("delete from evolvxsi_audit_event where actor_email = :e and row_hash is null"), {"e": f"admin-{RUN}@example.com"})
        s.commit()


def _search_as(idx, user_id) -> set[str]:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        user = s.get(User, user_id)
        acl = _get_acl_for_user(user, s)
    chunks = idx.semantic_retrieval(
        query_embedding=_vector("anything"),
        filters=IndexFilters(access_control_list=sorted(acl), tenant_id=TENANT),
        num_to_retrieve=10,
    )
    return {c.document_id for c in chunks}


def test_document_carries_only_the_data_access_group(world) -> None:  # type: ignore[no-untyped-def]
    _ids, access, _idx = world
    assert access[DOC_ID].user_groups == {f"research-{RUN}"}
    assert not access[DOC_ID].is_public


def test_sync_restricted_source_grants_nothing_through_groups(world) -> None:  # type: ignore[no-untyped-def]
    ids, access, idx = world
    assert access[SYNC_DOC_ID].user_groups == set()
    assert SYNC_DOC_ID not in _search_as(idx, ids["syncmember"])


def test_managing_a_source_grants_no_reading(world) -> None:  # type: ignore[no-untyped-def]
    ids, _access, idx = world
    assert DOC_ID not in _search_as(idx, ids["manager"])


def test_member_finds_it_and_outsider_does_not(world) -> None:  # type: ignore[no-untyped-def]
    ids, _access, idx = world
    assert DOC_ID in _search_as(idx, ids["member"])
    assert DOC_ID not in _search_as(idx, ids["outsider"])


def _resync(idx, doc_id: str) -> None:  # type: ignore[no-untyped-def]
    """What the background metadata sync does for one marked document."""
    with get_session_with_current_tenant() as s:
        access = get_access_for_document(doc_id, s)
    idx.update([MetadataUpdateRequest(document_ids=[doc_id], doc_id_to_chunk_cnt={doc_id: 1}, access=access)])
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    requests.post(f"http://{host}:9200/{idx._index_name}/_refresh", timeout=10)


def _dirty(doc_id: str) -> bool:
    with get_session_with_current_tenant() as s:
        d = s.get(Document, doc_id)
        return d.last_modified is not None and (d.last_synced is None or d.last_modified > d.last_synced)


def test_removing_a_group_from_a_source_reaches_the_index_after_resync(world) -> None:  # type: ignore[no-untyped-def]
    ids, _access, idx = world
    admin = SimpleNamespace(id=uuid.uuid4(), email=f"admin-{RUN}@example.com")
    with get_session_with_current_tenant() as s:
        s.query(Document).filter_by(id=DOC_ID).update({"last_synced": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)})
        s.commit()
    assert not _dirty(DOC_ID)
    with get_session_with_current_tenant() as s:
        result = set_source_groups(ids["ccs"][0], SourceGroupsUpdate(group_ids=[]), user=admin, db_session=s)
    assert result.documents_marked_for_resync == 1
    assert _dirty(DOC_ID)
    # Before the sync runs, the index still holds the old access list.
    assert DOC_ID in _search_as(idx, ids["member"])
    _resync(idx, DOC_ID)
    assert DOC_ID not in _search_as(idx, ids["member"])

    # Put it back for the remaining tests.
    with get_session_with_current_tenant() as s:
        set_source_groups(ids["ccs"][0], SourceGroupsUpdate(group_ids=[ids["research"]]), user=admin, db_session=s)
    _resync(idx, DOC_ID)
    assert DOC_ID in _search_as(idx, ids["member"])


def test_source_group_rules(world) -> None:  # type: ignore[no-untyped-def]
    ids, _access, _idx = world
    admin = SimpleNamespace(id=uuid.uuid4(), email=f"admin-{RUN}@example.com")
    with get_session_with_current_tenant() as s:
        default_group = s.query(__import__("nortpole.db.models", fromlist=["UserGroup"]).UserGroup).filter_by(is_default=True).first()
        # A permission-synced source needs at least one reading group.
        with pytest.raises(NortPoleError):
            set_source_groups(ids["ccs"][1], SourceGroupsUpdate(group_ids=[]), user=admin, db_session=s)
        s.rollback()
        # Unknown groups are refused.
        with pytest.raises(NortPoleError):
            set_source_groups(ids["ccs"][0], SourceGroupsUpdate(group_ids=[999999999]), user=admin, db_session=s)
        s.rollback()
        if default_group is not None:
            with pytest.raises(NortPoleError):
                set_source_groups(ids["ccs"][0], SourceGroupsUpdate(group_ids=[default_group.id]), user=admin, db_session=s)
            s.rollback()
        # Setting the same groups again marks nothing.
        same = set_source_groups(ids["ccs"][0], SourceGroupsUpdate(group_ids=[ids["research"]]), user=admin, db_session=s)
        assert same.documents_marked_for_resync == 0


def test_removal_from_the_group_takes_effect_on_the_next_search(world) -> None:  # type: ignore[no-untyped-def]
    ids, _access, idx = world
    with get_session_with_current_tenant() as s:
        s.query(User__UserGroup).filter_by(user_id=ids["member"]).delete()
        s.commit()
    assert DOC_ID not in _search_as(idx, ids["member"])
