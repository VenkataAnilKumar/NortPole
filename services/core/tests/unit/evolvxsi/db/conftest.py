"""Fixtures for the database-layer unit tests."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db_session() -> MagicMock:
    """A stand-in session: tests set the return values they need and assert on the calls made."""
    return MagicMock()
