"""Root conftest — shared fixtures available to all test directories."""

import os

# LiteLLM downloads its model cost map at import time unless this is set, so
# capability and pricing assertions would otherwise depend on upstream data
# that changes without notice. Pin the bundled copy to keep tests hermetic.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import importlib.util  # noqa: E402
from collections.abc import Generator  # noqa: E402
from contextlib import contextmanager  # noqa: E402

import pytest  # noqa: E402

from nortpole.utils.variable_functionality import (  # noqa: E402
    fetch_versioned_implementation,
    global_version,
)


@contextmanager
def _ee_enabled() -> Generator[None, None, None]:
    """Enables EE mode, then restores the previous EE state and clears the
    versioned-implementation cache so state doesn't leak between tests."""
    was_ee = global_version.is_ee_version()
    global_version.set_ee()
    fetch_versioned_implementation.cache_clear()
    try:
        yield
    finally:
        if not was_ee:
            global_version.unset_ee()
        fetch_versioned_implementation.cache_clear()


def _skip_without_ee() -> None:
    """NortPole ships the community edition only. A test that switches on Enterprise mode tests code this
    repository does not contain, so it is skipped (with this reason) rather than reported as a failure."""
    if importlib.util.find_spec("ee") is None:
        pytest.skip("Enterprise (ee) package is not part of NortPole")


@pytest.fixture()
def enable_ee() -> Generator[None, None, None]:
    """Temporarily enable EE mode for a single test."""
    _skip_without_ee()
    with _ee_enabled():
        yield


@pytest.fixture(scope="module")
def enable_ee_module() -> Generator[None, None, None]:
    """Enable EE mode for a module, e.g. for a module-scoped fixture, which
    runs before the function-scoped ``enable_ee``."""
    _skip_without_ee()
    with _ee_enabled():
        yield
