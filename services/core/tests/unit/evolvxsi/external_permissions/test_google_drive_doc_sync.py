"""Google Drive sharing to an NortPole access list, on recorded Drive API response shapes (no network).

Rules under test: named people may read; groups are recorded but grant nothing until group sync exists; domain sharing
and "anyone" links grant nothing (a link never makes a file public here); removed permissions grant nothing; addresses
are lowercased; unreadable permissions grant only the person whose access found the file.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from evolvxsi.access.models import ExternalAccess
from evolvxsi.access.utils import prefix_external_group, prefix_user_email
from evolvxsi.external_permissions.google_drive import doc_sync

RESPONSES = json.loads((Path(__file__).parent / "drive_responses.json").read_text())


class _Denied(Exception):
    """What the gateway raises when Drive returns 403/404 for a permissions read."""


class FakeOps:
    """The one gateway call the module makes, answering from the recorded pages."""

    def __init__(self, pages: dict[str, list[dict[str, Any]]], readable_by: set[str] | None = None) -> None:
        self.pages, self.readable_by, self.calls = pages, readable_by, []

    def list_file_permissions(self, *, user_email: str, file_id: str, fields: str):  # type: ignore[no-untyped-def]
        self.calls.append((user_email, file_id, fields))
        if file_id not in self.pages or (self.readable_by is not None and user_email not in self.readable_by):
            raise _Denied(f"403 for {user_email}")
        for page in self.pages[file_id]:
            yield from page["permissions"]


def _access(file: dict[str, Any], ops: FakeOps | None = None, **kw: Any) -> ExternalAccess:
    return doc_sync.get_external_access_for_raw_gdrive_file(
        file, "example.com", ops or FakeOps({}), kw.get("retriever", "ann.owner@gmail.com"), kw.get("admin", "admin@gmail.com"),
        kw.get("fallback", "ann.owner@gmail.com"), kw.get("add_prefix", False), kw.get("fallback_retriever"),
    )


def test_named_people_read_and_nothing_else_grants_access() -> None:
    a = _access(RESPONSES["my_drive_file"])
    assert a.external_user_emails == {"ann.owner@gmail.com", "bob.reader@gmail.com", "cara@gmail.com"}, "owner, reader, commenter; lowercased; removed one dropped"
    assert a.external_user_group_ids == {"finance-team@example.com"}, "a group is recorded"
    assert a.is_public is False, "neither domain sharing nor an anyone-with-the-link permission makes it public"


def test_a_public_on_the_web_file_is_still_only_for_the_people_named() -> None:
    a = _access(RESPONSES["public_on_the_web_file"])
    assert a.is_public is False and a.external_user_emails == {"ann.owner@gmail.com"}


def test_shared_drive_permissions_are_fetched_across_pages() -> None:
    ops = FakeOps({"1XyzSharedDriveSheet": RESPONSES["shared_drive_permission_pages"]})
    a = _access(RESPONSES["shared_drive_file"], ops)
    assert a.external_user_emails == {"dana@gmail.com", "eve@gmail.com"} and a.is_public is False
    assert ops.calls[0][0] == "ann.owner@gmail.com" and "permissions(" in ops.calls[0][2] and "nextPageToken" in ops.calls[0][2]


def test_the_next_reader_is_tried_when_one_cannot_read_the_permissions() -> None:
    ops = FakeOps({"1XyzSharedDriveSheet": RESPONSES["shared_drive_permission_pages"]}, readable_by={"admin@gmail.com"})
    a = _access(RESPONSES["shared_drive_file"], ops, fallback_retriever="other@gmail.com")
    assert [c[0] for c in ops.calls] == ["ann.owner@gmail.com", "other@gmail.com", "admin@gmail.com"]
    assert a.external_user_emails == {"dana@gmail.com", "eve@gmail.com"}


def test_unreadable_permissions_grant_only_the_person_who_found_the_file() -> None:
    a = _access(RESPONSES["externally_owned_file"], FakeOps({}), fallback="Bob.Reader@gmail.com")
    assert (a.external_user_emails, a.external_user_group_ids, a.is_public) == ({"bob.reader@gmail.com"}, set(), False)


def test_group_ids_are_prefixed_for_the_indexing_path() -> None:
    a = _access(RESPONSES["my_drive_file"], add_prefix=True)
    (group,) = a.external_user_group_ids
    assert group != "finance-team@example.com" and group.endswith("finance-team@example.com")


def test_an_unreadable_folder_grants_nothing() -> None:
    a = doc_sync.get_external_access_for_folder({"id": "f1", "permissionIds": ["x"]}, "example.com", FakeOps({}), "ann.owner@gmail.com")
    assert (a.external_user_emails, a.external_user_group_ids, a.is_public) == (set(), set(), False)


def test_the_drive_connector_hook_now_reaches_this_implementation() -> None:
    from evolvxsi.connectors.google_drive import doc_conversion

    a = doc_conversion._get_external_access_for_raw_gdrive_file(
        RESPONSES["my_drive_file"], "example.com", FakeOps({}), "ann.owner@gmail.com", "admin@gmail.com", "ann.owner@gmail.com",
    )
    assert isinstance(a, ExternalAccess) and "bob.reader@gmail.com" in a.external_user_emails, "not the no-op fallback"


@pytest.mark.parametrize("email", ["bob.reader@gmail.com", "Bob.Reader@Gmail.com"])
def test_a_person_matches_the_access_list_whatever_the_case_of_their_address(email: str) -> None:
    from types import SimpleNamespace

    from evolvxsi.access.access import _get_acl_for_user

    a = _access(RESPONSES["my_drive_file"])
    acl = {prefix_user_email(e) for e in a.external_user_emails} | {prefix_external_group(g) for g in a.external_user_group_ids}
    user = SimpleNamespace(email=email, prior_emails=[], is_anonymous=False, id=None)
    from unittest.mock import patch

    with patch("evolvxsi.access.access.group_names_for_user", return_value=set()):
        assert _get_acl_for_user(user, db_session=object()) & acl  # type: ignore[arg-type]
