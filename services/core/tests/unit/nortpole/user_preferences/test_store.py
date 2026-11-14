from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from nortpole.key_value_store.interface import KvKeyNotFoundError
from nortpole.user_preferences import store
from nortpole.user_preferences.store import QuietHours, UserPreferences


def _kv(data: dict) -> MagicMock:
    kv = MagicMock()

    def load(key: str):  # type: ignore[no-untyped-def]
        if key not in data:
            raise KvKeyNotFoundError()
        return data[key]

    kv.load.side_effect = load
    kv.store.side_effect = lambda k, v: data.__setitem__(k, v)
    return kv


def test_defaults_when_nothing_is_stored() -> None:
    with patch.object(store, "get_kv_store", return_value=_kv({})):
        p = store.load_preferences("u1")
    assert p.default_route == "auto"
    assert p.notifications.approvals and p.notifications.run_updates
    assert not p.notifications.quiet_hours.enabled


def test_each_user_has_their_own_record() -> None:
    data: dict = {}
    with patch.object(store, "get_kv_store", return_value=_kv(data)):
        store.save_preferences("u1", UserPreferences(default_route="local"))
        assert store.load_preferences("u1").default_route == "local"
        assert store.load_preferences("u2").default_route == "auto"


def test_damaged_record_falls_back_to_defaults() -> None:
    with patch.object(
        store, "get_kv_store", return_value=_kv({"evolvxsi_user_prefs:u1": {"default_route": "moon"}})
    ):
        assert store.load_preferences("u1").default_route == "auto"


def test_unknown_route_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UserPreferences(default_route="moon")  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["25:00", "7:00", "ab:cd", "12:60"])
def test_quiet_hours_need_a_valid_time(bad: str) -> None:
    with pytest.raises(ValidationError):
        QuietHours(start=bad)
