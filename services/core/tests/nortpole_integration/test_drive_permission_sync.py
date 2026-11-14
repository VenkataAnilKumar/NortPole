"""Stored source access lists are honoured (A5, Google Drive permission sync), on the real database.

A document from a "sync" source carries the access list the connector reported (as the indexing pipeline stores it).
The access builder must turn it into entries that match the people named, whatever the case of their address, and
nobody else; documents from other sources are unchanged. No search index is needed: this checks the access lists the
index would receive.
"""

import uuid

import pytest

from nortpole.access.access import _get_acl_for_user, get_access_for_document, get_access_for_documents
from nortpole.configs.constants import DocumentSource
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import AccessType, ConnectorCredentialPairStatus
from nortpole.db.models import Connector, ConnectorCredentialPair, Credential, Document, DocumentByConnectorCredentialPair, User
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

RUN = uuid.uuid4().hex[:8]


def _source(s, tag, access_type):  # type: ignore[no-untyped-def]
    connector = Connector(name=f"c-{tag}-{RUN}", source=DocumentSource.GOOGLE_DRIVE, connector_specific_config={})
    credential = Credential(name=f"cr-{tag}-{RUN}", source=DocumentSource.GOOGLE_DRIVE, credential_json={})
    s.add_all([connector, credential])
    s.flush()
    cc = ConnectorCredentialPair(name=f"cc-{tag}-{RUN}", connector_id=connector.id, credential_id=credential.id,
                                 status=ConnectorCredentialPairStatus.ACTIVE, access_type=access_type)
    s.add(cc)
    s.flush()
    return connector, credential, cc


def _doc(s, doc_id, connector, credential, **external):  # type: ignore[no-untyped-def]
    s.add(Document(id=doc_id, semantic_id=doc_id, from_ingestion_api=False, chunk_count=1, **external))
    s.flush()
    s.add(DocumentByConnectorCredentialPair(id=doc_id, connector_id=connector.id, credential_id=credential.id, has_been_indexed=True))
    s.flush()


@pytest.fixture()
def world():  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        sync_c, sync_cr, sync_cc = _source(s, "sync", AccessType.SYNC)
        pub_c, pub_cr, pub_cc = _source(s, "pub", AccessType.PUBLIC)
        ids = {"synced": f"drive-sync-{RUN}", "public": f"drive-pub-{RUN}", "unreadable": f"drive-none-{RUN}"}
        # What the indexing pipeline stores from the connector's access list for a "sync" source.
        _doc(s, ids["synced"], sync_c, sync_cr, external_user_emails=[f"bob-{RUN}@gmail.com"],
             external_user_group_ids=[f"finance-{RUN}@example.com"], is_public=False)
        _doc(s, ids["unreadable"], sync_c, sync_cr)  # a "sync" document with no access list grants nobody
        _doc(s, ids["public"], pub_c, pub_cr)
        users = [User(id=uuid.uuid4(), email=e, hashed_password="x", is_active=True, is_verified=True)
                 for e in (f"Bob-{RUN}@Gmail.com", f"carol-{RUN}@gmail.com")]
        s.add_all(users)
        s.commit()
        state = {**ids, "bob": users[0].id, "carol": users[1].id, "ccs": [sync_cc.id, pub_cc.id],
                 "connectors": [sync_c.id, pub_c.id], "creds": [sync_cr.id, pub_cr.id]}
    yield state
    with get_session_with_current_tenant() as s:
        s.query(DocumentByConnectorCredentialPair).filter(DocumentByConnectorCredentialPair.id.in_(list(ids.values()))).delete(synchronize_session=False)
        s.query(Document).filter(Document.id.in_(list(ids.values()))).delete(synchronize_session=False)
        s.query(ConnectorCredentialPair).filter(ConnectorCredentialPair.id.in_(state["ccs"])).delete(synchronize_session=False)
        s.query(Connector).filter(Connector.id.in_(state["connectors"])).delete(synchronize_session=False)
        s.query(Credential).filter(Credential.id.in_(state["creds"])).delete(synchronize_session=False)
        s.query(User).filter(User.id.in_([state["bob"], state["carol"]])).delete(synchronize_session=False)
        s.commit()


def test_a_synced_document_is_readable_by_the_people_drive_named_and_nobody_else(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        acl = get_access_for_document(world["synced"], s).to_acl()
        bob, carol = s.get(User, world["bob"]), s.get(User, world["carol"])
        assert _get_acl_for_user(bob, s) & acl, "Bob is named on the file (his NortPole address differs only in case)"
        assert not (_get_acl_for_user(carol, s) & acl), "Carol is not named"
        assert get_access_for_document(world["synced"], s).is_public is False, "no anyone-with-the-link exception"


def test_the_batch_builder_agrees_and_other_documents_are_unchanged(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        batch = get_access_for_documents([world["synced"], world["public"], world["unreadable"]], s)
        assert batch[world["synced"]].to_acl() == get_access_for_document(world["synced"], s).to_acl()
        assert batch[world["public"]].is_public is True, "a public source stays public"
        carol = s.get(User, world["carol"])
        assert not (_get_acl_for_user(carol, s) & batch[world["unreadable"]].to_acl()), "no access list grants nobody"
        assert batch[world["unreadable"]].is_public is False
