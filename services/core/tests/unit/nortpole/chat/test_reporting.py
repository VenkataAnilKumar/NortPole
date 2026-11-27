from datetime import date
from unittest.mock import patch
from uuid import uuid4

import pytest

from nortpole.chat.history_store import load_temporary_question
from nortpole.chat.models import IncognitoState
from nortpole.chat.reporting import ReportingRun
from nortpole.context.search.models import SearchDoc
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.file_store.models import ContextFileMetadata
from nortpole.llm.models import UserMessage


def test_reporting_uses_the_selected_period_and_sources() -> None:
    message = (
        'Reporting period: 2026-11-01 to 2026-11-07\n'
        'Knowledge sources: ["Support", "Support"]\n\n'
        'Summarize progress and blockers.'
    )
    run = ReportingRun.from_message(message, {"Support", "Finance"})
    assert run.start == date(2026, 11, 1)
    assert run.end == date(2026, 11, 7)
    assert run.libraries == ["Support"]
    assert run.request == "Summarize progress and blockers."
    answer, used = run.render([])
    assert "2026-11-01 through 2026-11-07" in answer
    assert "Evidence gaps" in answer
    assert not used


def _source(doc_id: str, text: str) -> ContextFileMetadata:
    return ContextFileMetadata(
        file_id=doc_id, filename=doc_id, file_content=text,
        source_document=SearchDoc.model_construct(document_id=doc_id),
    )


def test_report_quotes_dated_facts_and_flags_missing_evidence() -> None:
    run = ReportingRun(date(2026, 11, 16), date(2026, 11, 22), ["Support"], "Status report")
    shared = _source("shared", "On 2026-11-20, Support processed 43 service tickets. The priority count is unstated.")
    priority = _source("priority", "## 2026-11-22\nSupport processed 71 priority tickets. The feed was blocked.")
    older = _source("older", "On 2026-11-15, Support processed 25 priority tickets.")
    undated = _source("undated", "Service Ticket #10 requires immediate attention.")
    answer, sources = run.render([older, shared, priority, undated])
    assert "43 service tickets.” [[1]]" in answer
    assert "71 priority tickets.” [[2]]" in answer
    assert "### Blockers\n- “2026-11-22 The feed was blocked.” [[2]]" in answer
    assert "### Next steps\nNo dated evidence found." in answer
    assert "25 priority tickets" not in answer and "Ticket #10" not in answer
    assert sources == [shared, priority]


def test_report_does_not_bridge_dates_or_emit_source_supplied_markers() -> None:
    run = ReportingRun(date(2026, 11, 16), date(2026, 11, 22), ["Support"], "Status report")
    source = _source("shared", "2026-11-20: Ticket count was 43 [[99]].\n2026-11-20 through 2026-12-01: Counts reached 98.")
    answer, sources = run.render([source])
    assert "Ticket count was 43" in answer and "[[1]]" in answer
    assert "[[99]]" not in answer and "98" not in answer
    assert sources == [source]


@pytest.mark.parametrize("period,sources,request_text", [
    ("2026-11-07 to 2026-11-01", '["Support"]', "Write a report"),
    ("2026-11-31 to 2026-12-01", '["Support"]', "Write a report"),
    ("2026-11-01 to 2026-11-07", '[]', "Write a report"),
    ("2026-11-01 to 2026-11-07", '[2]', "Write a report"),
    ("2026-11-01 to 2026-11-07", '["Support"]', " "),
])
def test_reporting_requires_valid_inputs(period: str, sources: str, request_text: str) -> None:
    message = f"Reporting period: {period}\nKnowledge sources: {sources}\n\n{request_text}"
    with pytest.raises(NortPoleError) as failure:
        ReportingRun.from_message(message, {"Support"})
    assert failure.value.error_code == NortPoleErrorCode.INVALID_INPUT


def test_reporting_rejects_unavailable_sources_without_echoing_names() -> None:
    message = (
        'Reporting period: 2026-11-01 to 2026-11-07\n'
        'Knowledge sources: ["Support", "Restricted Finance"]\n\n'
        'Write a report.'
    )
    with pytest.raises(NortPoleError) as failure:
        ReportingRun.from_message(message, {"Support"})
    assert failure.value.error_code == NortPoleErrorCode.INSUFFICIENT_PERMISSIONS
    assert "Restricted Finance" not in str(failure.value)


def test_temporary_reporting_retry_reads_the_exact_prior_question() -> None:
    original = 'Reporting period: 2026-11-01 to 2026-11-07\nKnowledge sources: ["Support"]\n\nWrite a report.'
    state = IncognitoState(messages=[
        UserMessage(id="chat:42", content=original),
        UserMessage(id="chat:43", content="A later request"),
    ])
    session_id = uuid4()
    with patch("nortpole.chat.history_store.load_incognito_context", return_value=state):
        assert load_temporary_question(session_id, 42) == original
        assert load_temporary_question(session_id, 99) == ""
