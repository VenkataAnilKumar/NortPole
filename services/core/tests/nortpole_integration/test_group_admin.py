"""Access-group management on the real database. Skips without Postgres."""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from nortpole.configs.constants import DocumentSource
from nortpole.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant
from nortpole.db.enums import AccessType, ConnectorCredentialPairStatus
from nortpole.db.models import (
    Connector,
    ConnectorCredentialPair,
    Credential,
    User,
    UserGroup,
    UserGroup__CCPairDataAccess,
)
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.knowledge.knowledge_access import group_admin as ga
from nortpole.knowledge.knowledge_access.groups import group_names_for_user


def _up() -> bool:
    try:
        SqlEngine.init_engine(pool_size=2, max_overflow=0)
    except Exception:
        pass  # already initialised by another test module
    try:
        with get_session_with_current_tenant() as s:
            s.execute(text("select 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

RUN = uuid.uuid4().hex[:8]
ADMIN = SimpleNamespace(id=uuid.uuid4(), email=f"admin-{RUN}@example.com")


@pytest.fixture(scope="module")
def people():  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        users = [
            User(id=uuid.uuid4(), email=f"ga{i}-{RUN}@example.com", hashed_password="x", is_active=True, is_verified=True)
            for i in range(2)
        ]
        s.add_all(users)
        s.commit()
        ids = [u.id for u in users]
    yield ids
    with get_session_with_current_tenant() as s:
        s.execute(text("delete from user__user_group where user_id = any(:ids)"), {"ids": ids})
        s.execute(text("delete from user_group where name like :p"), {"p": f"%{RUN}%"})
        s.query(User).filter(User.id.in_(ids)).delete()
        s.execute(text("delete from evolvxsi_audit_event where actor_email = :e and row_hash is null"), {"e": ADMIN.email})
        s.commit()


def test_create_list_and_membership(people) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        g = ga.create_group(ga.GroupCreate(name=f"  Research   {RUN} ", user_ids=[people[0]]), user=ADMIN, db_session=s)
        assert g.name == f"Research {RUN}"
        assert [m.id for m in g.members] == [people[0]]
        assert group_names_for_user(s, people[0]) >= {g.name}
        assert g.name in {x.name for x in ga.list_groups(_=ADMIN, db_session=s)}

        # Replacing the member list removes the first person at once.
        g2 = ga.update_group(g.id, ga.GroupUpdate(user_ids=[people[1]]), user=ADMIN, db_session=s)
        assert [m.id for m in g2.members] == [people[1]]
        assert g.name not in group_names_for_user(s, people[0])


def test_duplicate_name_is_refused_whatever_the_case(people) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s, pytest.raises(NortPoleError):
        ga.create_group(ga.GroupCreate(name=f"research {RUN}"), user=ADMIN, db_session=s)


def test_unknown_user_is_refused(people) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s, pytest.raises(NortPoleError):
        ga.create_group(ga.GroupCreate(name=f"Ghosts {RUN}", user_ids=[uuid.uuid4()]), user=ADMIN, db_session=s)


def test_empty_name_is_refused() -> None:
    with pytest.raises(ValueError):
        ga.GroupCreate(name="   ")


def test_built_in_groups_are_not_managed_here(people) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        default = s.query(UserGroup).filter_by(is_default=True).first()
        if default is None:
            pytest.skip("no built-in group in this database")
        with pytest.raises(NortPoleError):
            ga.update_group(default.id, ga.GroupUpdate(user_ids=[]), user=ADMIN, db_session=s)
        with pytest.raises(NortPoleError):
            ga.delete_group(default.id, user=ADMIN, db_session=s)


def test_group_that_reads_a_source_cannot_be_renamed_or_deleted(people) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        g = ga.create_group(ga.GroupCreate(name=f"Finance {RUN}"), user=ADMIN, db_session=s)
        connector = Connector(name=f"gac-{RUN}", source=DocumentSource.FILE, connector_specific_config={})
        credential = Credential(name=f"gacr-{RUN}", source=DocumentSource.FILE, credential_json={})
        s.add_all([connector, credential])
        s.flush()
        cc = ConnectorCredentialPair(name=f"gacc-{RUN}", connector_id=connector.id, credential_id=credential.id,
                                     status=ConnectorCredentialPairStatus.ACTIVE, access_type=AccessType.PRIVATE)
        s.add(cc)
        s.flush()
        s.add(UserGroup__CCPairDataAccess(cc_pair_id=cc.id, user_group_id=g.id, access_type=AccessType.PRIVATE))
        s.commit()
        try:
            view = next(x for x in ga.list_groups(_=ADMIN, db_session=s) if x.id == g.id)
            assert [src.cc_pair_id for src in view.sources] == [cc.id]
            with pytest.raises(NortPoleError):
                ga.update_group(g.id, ga.GroupUpdate(name=f"Money {RUN}"), user=ADMIN, db_session=s)
            with pytest.raises(NortPoleError):
                ga.delete_group(g.id, user=ADMIN, db_session=s)
            # Members can still change while the group reads a source.
            ga.update_group(g.id, ga.GroupUpdate(user_ids=[people[0]]), user=ADMIN, db_session=s)
        finally:
            s.rollback()
            s.query(UserGroup__CCPairDataAccess).filter_by(cc_pair_id=cc.id).delete()
            s.query(ConnectorCredentialPair).filter_by(id=cc.id).delete()
            s.query(Credential).filter_by(id=credential.id).delete()
            s.query(Connector).filter_by(id=connector.id).delete()
            s.commit()
        # Once it reads no source, both are allowed.
        renamed = ga.update_group(g.id, ga.GroupUpdate(name=f"Money {RUN}"), user=ADMIN, db_session=s)
        assert renamed.name == f"Money {RUN}"
        ga.delete_group(g.id, user=ADMIN, db_session=s)
        assert s.get(UserGroup, g.id) is None
