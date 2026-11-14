"""The model client redacts per route policy, using the real client and database."""

from unittest.mock import patch

import pytest

from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.llm.factory import get_default_llm
from evolvxsi.llm.models import GenerationRequest, UserMessage
from evolvxsi.governance.redaction import request as req
from evolvxsi.governance.redaction.request import EvolvXSIRedactionCount
from tests.evolvxsi_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres and a default model")


@pytest.fixture(autouse=True)
def _clean():  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        s.query(EvolvXSIRedactionCount).delete()
        s.commit()
    yield


def _sent(llm, text: str) -> str:  # type: ignore[no-untyped-def]
    messages, _ = llm._prepare_request(GenerationRequest(messages=[UserMessage(content=text)]))
    return repr(messages)


def test_the_real_client_redacts_on_a_cloud_route_and_counts_it() -> None:
    llm = get_default_llm()
    with patch.object(req, "_route_kind", return_value="cloud"):
        sent = _sent(llm, "Write to jane@corp.com and charge 4111 1111 1111 1111")
    assert "jane@corp.com" not in sent and "4111" not in sent
    assert "[REDACTED:EMAIL]" in sent and "[REDACTED:CARD]" in sent
    with get_session_with_current_tenant() as s:
        rows = {(r.route_kind, r.data_kind): r.items for r in s.query(EvolvXSIRedactionCount)}
    assert rows == {("cloud", "EMAIL"): 1, ("cloud", "CARD"): 1}


def test_the_real_client_leaves_a_local_route_untouched_by_default() -> None:
    llm = get_default_llm()
    with patch.object(req, "_route_kind", return_value="local"):
        assert "jane@corp.com" in _sent(llm, "Write to jane@corp.com")
    with get_session_with_current_tenant() as s:
        assert s.query(EvolvXSIRedactionCount).count() == 0


def test_the_trace_input_is_built_from_the_redacted_request() -> None:
    """Spans are built from the serialised messages, which come after redaction."""
    llm = get_default_llm()
    with patch.object(req, "_route_kind", return_value="cloud"):
        messages, _ = llm._prepare_request(GenerationRequest(messages=[UserMessage(content="secret sk-abcdefghijklmnop1234")]))
    assert "sk-abcdefghijklmnop1234" not in repr(messages)
