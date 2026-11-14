"""The search-time source check (cc-pair access filter) in enforced mode (A5).

With enforcement, which sources a person may read is computed from the
database on every search, so group changes apply at once instead of waiting
for documents to be re-synced. Checked against the real database and
OpenSearch:

* PRIVATE source: a reading-group member finds its documents; others do not;
  removing the group from the source hides them immediately (before re-sync),
  while the old document-list filter would still show them.
* SYNC_RESTRICTED source: visible only to someone who is in a reading group
  AND allowed by the document's own access list.

The rollout gate (flag plus index backfill state) is stubbed to ENFORCE; it
decides when enforcement is switched on, not who sees what.
"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from sqlalchemy import text

from nortpole.access.access import get_access_for_documents
from nortpole.access.models import DocumentAccess
from nortpole.context.search.models import CCPairAccessMode, IndexFilters
from nortpole.context.search.preprocessing.access_filters import build_access_filters_for_user
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import AccessType, VectorQuantization
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
)
from nortpole.document_index.interfaces import IndexingMetadata, TenantState
from nortpole.document_index.opensearch.opensearch_document_index import OpenSearchDocumentIndex
from nortpole.knowledge.knowledge_access.group_admin import SourceGroupsUpdate, set_source_groups
from tests.nortpole_integration.test_group_access import _doc, _source, _up
from tests.nortpole_integration.test_retrieval_acl import DIM, TENANT, _chunk, _vector

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres and OpenSearch")

RUN = uuid.uuid4().hex[:8]
PRIV = f"enf-priv-{RUN}"
SYNC = f"enf-sync-{RUN}"
HOST = os.environ.get("OPENSEARCH_HOST", "localhost")
ADMIN = SimpleNamespace(id=uuid.uuid4(), email=f"admin-{RUN}@example.com")


@pytest.fixture(scope="module")
def world():  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        users = {
            n: User(id=uuid.uuid4(), email=f"{n}-{RUN}@example.com", hashed_password="x", is_active=True, is_verified=True)
            for n in ("member", "outsider", "syncmember", "syncnamed_only")
        }
        groups = {n: UserGroup(name=f"enf-{n}-{RUN}", is_up_to_date=True) for n in ("research", "syncgroup")}
        s.add_all([*users.values(), *groups.values()])
        s.flush()
        c1, cr1, priv_cc = _source(s, f"enfp{RUN}", AccessType.PRIVATE)
        c2, cr2, sync_cc = _source(s, f"enfs{RUN}", AccessType.SYNC_RESTRICTED)
        s.add_all([
            User__UserGroup(user_id=users["member"].id, user_group_id=groups["research"].id),
            User__UserGroup(user_id=users["syncmember"].id, user_group_id=groups["syncgroup"].id),
            UserGroup__CCPairDataAccess(cc_pair_id=priv_cc.id, user_group_id=groups["research"].id, access_type=AccessType.PRIVATE),
            UserGroup__CCPairDataAccess(cc_pair_id=sync_cc.id, user_group_id=groups["syncgroup"].id, access_type=AccessType.SYNC_RESTRICTED),
        ])
        s.flush()
        _doc(s, PRIV, c1, cr1)
        _doc(s, SYNC, c2, cr2)
        s.commit()
        ids = {**{k: u.id for k, u in users.items()}, "groups": {k: g.id for k, g in groups.items()},
               "priv_cc": priv_cc.id, "sync_cc": sync_cc.id,
               "connectors": [c1.id, c2.id], "credentials": [cr1.id, cr2.id]}

    with get_session_with_current_tenant() as s:
        access = get_access_for_documents([PRIV], s)
    # The permission-synced document's own access list (as a source's sync
    # would write it): it names the synced member and one person outside the group.
    sync_access = DocumentAccess.build(
        user_emails=[], user_groups=[],
        external_user_emails=[f"syncmember-{RUN}@example.com", f"syncnamed_only-{RUN}@example.com"],
        external_user_group_ids=[], is_public=False,
    )
    name = f"evolvxsi_enf_test_{RUN}"
    idx = OpenSearchDocumentIndex(
        tenant_state=TenantState(tenant_id=TENANT, multitenant=False),
        index_name=name, embedding_dim=DIM, vector_quantization=VectorQuantization.NONE,
    )
    idx.verify_and_create_index_if_necessary(embedding_dim=DIM)
    chunks = [
        _chunk({"doc_id": PRIV, "title": PRIV, "text": "private research", "access": None}).model_copy(
            update={"access": access[PRIV], "cc_pair_ids": [ids["priv_cc"]]}),
        _chunk({"doc_id": SYNC, "title": SYNC, "text": "synced research", "access": None}).model_copy(
            update={"access": sync_access, "cc_pair_ids": [ids["sync_cc"]]}),
    ]
    idx.index(chunks, IndexingMetadata(doc_id_to_chunk_cnt_diff={d: IndexingMetadata.ChunkCounts(old_chunk_cnt=0, new_chunk_cnt=1) for d in (PRIV, SYNC)}))
    requests.post(f"http://{HOST}:9200/{name}/_refresh", timeout=10)
    yield ids, idx

    requests.delete(f"http://{HOST}:9200/{name}", timeout=10)
    with get_session_with_current_tenant() as s:
        s.query(DocumentByConnectorCredentialPair).filter(DocumentByConnectorCredentialPair.id.in_([PRIV, SYNC])).delete()
        s.query(Document).filter(Document.id.in_([PRIV, SYNC])).delete()
        s.query(UserGroup__CCPairDataAccess).filter(UserGroup__CCPairDataAccess.cc_pair_id.in_([ids["priv_cc"], ids["sync_cc"]])).delete()
        s.query(User__UserGroup).filter(User__UserGroup.user_group_id.in_(list(ids["groups"].values()))).delete()
        s.query(ConnectorCredentialPair).filter(ConnectorCredentialPair.id.in_([ids["priv_cc"], ids["sync_cc"]])).delete()
        s.query(Credential).filter(Credential.id.in_(ids["credentials"])).delete()
        s.query(Connector).filter(Connector.id.in_(ids["connectors"])).delete()
        s.query(UserGroup).filter(UserGroup.id.in_(list(ids["groups"].values()))).delete()
        s.query(User).filter(User.id.in_([ids[k] for k in ("member", "outsider", "syncmember", "syncnamed_only")])).delete()
        s.execute(text("delete from evolvxsi_audit_event where actor_email = :e and row_hash is null"), {"e": ADMIN.email})
        s.commit()


def _find(idx, user_id, enforce: bool) -> set[str]:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        user = s.get(User, user_id)
        mode = CCPairAccessMode.ENFORCE if enforce else None
        with patch("nortpole.context.search.preprocessing.access_filters.get_cc_pair_access_mode", return_value=mode), \
             patch("nortpole.context.search.preprocessing.access_filters.has_guarded_cc_pairs", return_value=False):
            uf = build_access_filters_for_user(user, s)
    filters = IndexFilters(access_control_list=uf.access_control_list, cc_pair_access=uf.cc_pair_access, tenant_id=TENANT)
    chunks = idx.semantic_retrieval(query_embedding=_vector("research"), filters=filters, num_to_retrieve=10)
    return {c.document_id for c in chunks}


def test_private_source_member_sees_it_and_outsider_does_not(world) -> None:  # type: ignore[no-untyped-def]
    ids, idx = world
    assert PRIV in _find(idx, ids["member"], enforce=True)
    assert PRIV not in _find(idx, ids["outsider"], enforce=True)


def test_sync_restricted_needs_group_and_document_permission(world) -> None:  # type: ignore[no-untyped-def]
    ids, idx = world
    # In the group and named on the document: visible.
    assert SYNC in _find(idx, ids["syncmember"], enforce=True)
    # Named on the document but not in the reading group: hidden.
    assert SYNC not in _find(idx, ids["syncnamed_only"], enforce=True)
    # Neither: hidden.
    assert SYNC not in _find(idx, ids["outsider"], enforce=True)


def test_removing_the_group_from_the_source_applies_at_once_when_enforced(world) -> None:  # type: ignore[no-untyped-def]
    ids, idx = world
    with get_session_with_current_tenant() as s:
        set_source_groups(ids["priv_cc"], SourceGroupsUpdate(group_ids=[]), user=ADMIN, db_session=s)
    # No re-sync has run, so the stored access list still names the group.
    assert PRIV in _find(idx, ids["member"], enforce=False), "the old filter shows the stale window"
    assert PRIV not in _find(idx, ids["member"], enforce=True), "enforcement closes it"
