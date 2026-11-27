import pytest

from nortpole.db.enums import ConnectorCredentialPairStatus, IndexingStatus
from nortpole.db.models import ConnectorCredentialPair
from nortpole.server.documents.connector import _indexing_readiness


@pytest.mark.parametrize(
    ("status", "attempt", "indexed", "expected"),
    [
        ("ACTIVE", "success", False, "configured"),
        ("ACTIVE", None, True, "ready"),
        ("SCHEDULED", None, False, "syncing"),
        ("ACTIVE", "in_progress", True, "syncing"),
        ("INITIAL_INDEXING", "failed", False, "attention"),
        ("ACTIVE", "completed_with_errors", True, "attention"),
        ("PAUSED", "failed", True, "paused"),
    ],
)
def test_indexing_readiness(status, attempt, indexed, expected):
    pair = ConnectorCredentialPair(status=ConnectorCredentialPairStatus(status))
    latest = IndexingStatus(attempt) if attempt else None

    assert _indexing_readiness(pair, latest, indexed) == expected
