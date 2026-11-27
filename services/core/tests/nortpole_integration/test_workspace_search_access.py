"""Check workspace search's database authorization against stale index candidates."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from nortpole.configs.constants import DocumentSource
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import AccessType, UserFileStatus
from nortpole.db.models import (
    User,
    User__UserGroup,
    UserFile,
    UserGroup,
    UserGroup__CCPairDataAccess,
)
from nortpole.server.features.search.workspace import authorized_workspace_destinations
from tests.nortpole_integration.test_group_access import _doc, _source, _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres and OpenSearch")


def test_stale_upload_candidates_are_checked_against_current_access() -> None:
    tag = uuid4().hex
    with get_session_with_current_tenant() as db:
        reader = User(
            id=uuid4(), email=f"search-reader-{tag}@example.com", hashed_password="x"
        )
        other = User(
            id=uuid4(), email=f"search-other-{tag}@example.com", hashed_password="x"
        )
        group = UserGroup(name=f"search-{tag}", is_up_to_date=True)
        db.add_all([reader, other, group])
        db.flush()

        connector, credential, pair = _source(db, tag, AccessType.PRIVATE)
        source_access = UserGroup__CCPairDataAccess(
            cc_pair_id=pair.id, user_group_id=group.id, access_type=AccessType.PRIVATE
        )
        db.add_all(
            [source_access, User__UserGroup(user_id=reader.id, user_group_id=group.id)]
        )
        doc_id = f"search-file-{tag}"
        _doc(db, doc_id, connector, credential)
        personal = UserFile(
            id=uuid4(),
            user_id=reader.id,
            file_id=f"search-{tag}",
            name="Upload.txt",
            file_type="text/plain",
            status=UserFileStatus.COMPLETED,
        )
        hidden = UserFile(
            id=uuid4(),
            user_id=reader.id,
            file_id=f"incognito-{tag}",
            name="Private.txt",
            file_type="text/plain",
            status=UserFileStatus.COMPLETED,
            incognito=True,
        )
        db.add_all([personal, hidden])
        db.flush()
        ranked = {
            doc_id: SimpleNamespace(source_type=DocumentSource.FILE),
            str(personal.id): SimpleNamespace(source_type=DocumentSource.USER_FILE),
            str(hidden.id): SimpleNamespace(source_type=DocumentSource.USER_FILE),
        }
        assert set(authorized_workspace_destinations(ranked, reader, db)) == {
            doc_id,
            str(personal.id),
        }
        assert not authorized_workspace_destinations(ranked, other, db)

        db.delete(source_access)
        personal.status = UserFileStatus.DELETING
        db.flush()
        assert not authorized_workspace_destinations(ranked, reader, db)
