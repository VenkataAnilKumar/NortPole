from unittest.mock import MagicMock

from evolvxsi.server.features.notifications import api


def test_polling_creates_no_upstream_seeded_notifications() -> None:
    user, db = MagicMock(), MagicMock()
    assert api._check_for_notifications_to_create(user, db) is None
    # Nothing was read or written: no seeded announcement, no changelog fetch.
    assert db.method_calls == []
    assert user.method_calls == []


def test_module_does_not_import_the_release_notes_fetcher() -> None:
    assert not hasattr(api, "ensure_release_notes_fresh_and_notify")
    assert not hasattr(api, "ensure_permissions_migration_notification")
    assert not hasattr(api, "ensure_build_mode_intro_notification")
