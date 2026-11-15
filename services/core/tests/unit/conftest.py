"""Unit-suite conftest.

Unit tests assume OSS resolution unless they opt into EE via the shared
``enable_ee`` fixture (see ``backend/tests/conftest.py``).
"""

from collections.abc import Generator
from unittest.mock import patch

import httpx
import pytest

from nortpole.utils.variable_functionality import (
    fetch_versioned_implementation,
    global_version,
)


@pytest.fixture(autouse=True)
def _no_remote_catalog_fetch() -> Generator[None, None, None]:
    """Keeps the unit suite offline: catalog misses must not reach GitHub.

    The fetch returns 404, which the catalog treats as no remote data. Raising
    instead would put the exception in a captured log record, and its
    traceback would keep the caller's frames alive.

    Remote-catalog tests override this by patching
    ``model_catalog._fetch_provider_file`` themselves. Patching that seam
    (rather than ``httpx.get``) keeps every other httpx caller working.
    """
    from nortpole.llm import model_catalog

    with patch.object(
        model_catalog,
        "_fetch_provider_file",
        return_value=httpx.Response(404),
    ):
        yield


@pytest.fixture(autouse=True)
def _reset_leaked_ee_state() -> Generator[None, None, None]:
    """Undoes EE state leaked into the process by import side effects.

    ``set_is_ee_if_available()`` runs at module level in ``nortpole.main``
    and every ``background/celery/versioned_apps`` module, and flips the
    process-global EE flag whenever the build ships the EE code. A
    unit test whose import chain reaches one of those modules therefore silently
    switches every later test in the worker to EE resolution, breaking
    OSS-asserting tests order-dependently. Runs before ``enable_ee`` (autouse
    fixtures are instantiated first), so opting in still works.
    """
    if global_version.is_ee_version():
        global_version.unset_ee()
        # Entries resolved while the flag was flipped point at EE
        # implementations; drop them along with the flag.
        fetch_versioned_implementation.cache_clear()
    yield


# NortPole's own governance tests: they exercise the real settings readers, including failing closed when the
# store cannot be read, so the neutral settings below are not applied to them.
_GOVERNANCE_TEST_DIRS = ("route_policy", "redaction", "tool_catalog", "extensions")


@pytest.fixture(autouse=True)
def _nortpole_governance_neutral(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Unit tests have no database. NortPole added governance that reads its settings from the key-value store on
    the request path (route policy and redaction, the MCP allowlist, the tool catalog), and with no store those
    readers fail closed: the inherited tests then see blocked MCP servers, withheld tools or a crashed model call
    instead of the behaviour they test.

    This gives every other unit test an in-memory store for the ``nortpole_`` keys only, holding neutral settings
    (no redaction, no MCP allowlist, every tool kind on), and passes the tool catalog's filter through. Other keys
    still reach the real store, as before. The governance itself is tested in its own unit folders (which opt out
    of this fixture) and against a real database in ``tests/nortpole_integration``.
    """
    parts = request.node.path.parts
    if any(d in parts for d in _GOVERNANCE_TEST_DIRS):
        yield
        return

    from nortpole.key_value_store.interface import KvKeyNotFoundError
    from nortpole.key_value_store.store import PgRedisKVStore
    from nortpole.governance.route_policy.policy import RoutePolicy
    from nortpole.governance.tool_catalog import catalog

    memory: dict[str, object] = {
        "nortpole_route_policy": RoutePolicy(redact_route_kinds=[]).model_dump(),
        "nortpole_tool_catalog": catalog.CatalogPolicy(kinds={k: True for k in catalog.KINDS}).model_dump(),
    }
    real_load, real_store, real_delete = PgRedisKVStore.load, PgRedisKVStore.store, PgRedisKVStore.delete

    def load(self, key, refresh_cache=False):  # type: ignore[no-untyped-def]
        if not key.startswith("nortpole_"):
            return real_load(self, key, refresh_cache)
        if key not in memory:
            raise KvKeyNotFoundError
        return memory[key]

    def store(self, key, val, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not key.startswith("nortpole_"):
            return real_store(self, key, val, *args, **kwargs)
        memory[key] = val

    def delete(self, key):  # type: ignore[no-untyped-def]
        if not key.startswith("nortpole_"):
            return real_delete(self, key)
        memory.pop(key, None)

    with patch.object(PgRedisKVStore, "load", load), patch.object(PgRedisKVStore, "store", store), \
            patch.object(PgRedisKVStore, "delete", delete), \
            patch.object(catalog, "filter_tools", lambda tools, db_session=None: tools):
        yield
