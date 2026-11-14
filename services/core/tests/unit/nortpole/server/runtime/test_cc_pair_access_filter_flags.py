from unittest.mock import MagicMock, patch

from nortpole.cache.interface import CacheBackendType
from nortpole.server.runtime import evolvxsi_runtime
from nortpole.server.runtime.evolvxsi_runtime import NortPoleRuntime


def test_cc_pair_access_flags_read_the_cache_backend() -> None:
    cache = MagicMock()
    cache.get.side_effect = lambda key: (
        b"true" if key.endswith("cc_pair_access_filter:enabled") else None
    )
    with (
        patch.object(evolvxsi_runtime, "get_cache_backend", return_value=cache),
        patch.object(evolvxsi_runtime, "ENFORCE_CC_PAIR_ACCESS_FILTER", False),
    ):
        assert NortPoleRuntime.get_cc_pair_access_filter_enabled()
        assert not NortPoleRuntime.get_cc_pair_access_filter_enforce()


def test_cc_pair_access_flags_fall_back_when_the_cache_fails() -> None:
    with (
        patch.object(
            evolvxsi_runtime, "get_cache_backend", side_effect=ConnectionError("down")
        ),
        patch.object(evolvxsi_runtime, "ENABLE_CC_PAIR_ACCESS_FILTER", False),
        patch.object(evolvxsi_runtime, "ENFORCE_CC_PAIR_ACCESS_FILTER", False),
    ):
        assert not NortPoleRuntime.get_cc_pair_access_filter_enabled()
        assert not NortPoleRuntime.get_cc_pair_access_filter_enforce()


def test_evolvxsi_defaults_turn_the_filter_on_and_enforce_it() -> None:
    """With no cache override, the NortPole defaults apply."""
    cache = MagicMock()
    cache.get.return_value = None
    with patch.object(evolvxsi_runtime, "get_cache_backend", return_value=cache):
        assert NortPoleRuntime.get_cc_pair_access_filter_enabled() is evolvxsi_runtime.ENABLE_CC_PAIR_ACCESS_FILTER
        assert NortPoleRuntime.get_cc_pair_access_filter_enforce() is evolvxsi_runtime.ENFORCE_CC_PAIR_ACCESS_FILTER
    assert evolvxsi_runtime.ENABLE_CC_PAIR_ACCESS_FILTER is True
    assert evolvxsi_runtime.ENFORCE_CC_PAIR_ACCESS_FILTER is True


def test_enforcement_waits_for_the_backfill() -> None:
    """Enforcement only applies once every chunk carries its source ids."""
    from nortpole.access import cc_pair_access
    from nortpole.context.search.models import CCPairAccessMode

    with (
        patch.object(cc_pair_access.NortPoleRuntime, "get_cc_pair_access_filter_enabled", return_value=True),
        patch.object(cc_pair_access.NortPoleRuntime, "get_cc_pair_access_filter_enforce", return_value=True),
        patch.object(cc_pair_access, "is_cc_pair_ids_backfill_complete", return_value=False),
    ):
        assert cc_pair_access.get_cc_pair_access_mode(MagicMock()) is CCPairAccessMode.SHADOW
    with (
        patch.object(cc_pair_access.NortPoleRuntime, "get_cc_pair_access_filter_enabled", return_value=True),
        patch.object(cc_pair_access.NortPoleRuntime, "get_cc_pair_access_filter_enforce", return_value=True),
        patch.object(cc_pair_access, "is_cc_pair_ids_backfill_complete", return_value=True),
    ):
        assert cc_pair_access.get_cc_pair_access_mode(MagicMock()) is CCPairAccessMode.ENFORCE


def test_postgres_cache_reads_the_current_tenant() -> None:
    """The Postgres cache has no cloud schema in a single-tenant install."""
    cache = MagicMock()
    cache.get.return_value = b"true"
    with (
        patch.object(evolvxsi_runtime, "CACHE_BACKEND", CacheBackendType.POSTGRES),
        patch.object(
            evolvxsi_runtime, "get_cache_backend", return_value=cache
        ) as get_cache_backend,
    ):
        assert NortPoleRuntime.get_cc_pair_access_filter_enabled()
    assert get_cache_backend.call_args.kwargs["tenant_id"] is None
