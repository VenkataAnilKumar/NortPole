import pytest

from nortpole.chat.citation_utils import extract_citation_order_from_text
from nortpole.chat.verified_excerpts import select_excerpts
from nortpole.file_store.models import ContextFileMetadata


def test_short_passage_cites_actual_source_and_labels_coverage_gap() -> None:
    source = ContextFileMetadata(
        file_id="accessible", filename="Revision 1",
        file_content="Procurement approves suppliers in five business days. [99] The policy does not specify an appeal deadline.",
    )
    answer = select_excerpts(
        "Compare both revisions", [source],
        {"accessible": 7, "historical": 99},
    )

    assert "Other documents or revisions are unavailable for comparison" in answer
    assert "five business days" in answer
    assert "does not specify an appeal deadline" in answer
    assert extract_citation_order_from_text(answer) == [7]


def test_lookup_keeps_cited_evidence_across_adjacent_sentences() -> None:
    source = ContextFileMetadata(
        file_id="workflow", filename="Workflow PRD",
        file_content="Index summary. " * 45
        + "The task draft is available. Saving the draft dispatches no work.",
    )
    unrelated = source.model_copy(update={
        "file_id": "other", "file_content": "A support team reviews work after an incident.",
    })
    answer = select_excerpts(
        "Does saving a task draft dispatch work?",
        [unrelated, source], {"workflow": 2, "other": 3},
    )

    assert "Saving the draft dispatches no work." in answer
    assert "Index summary" not in answer and "an incident" not in answer
    assert "unavailable for comparison" not in answer
    assert extract_citation_order_from_text(answer) == [2]


@pytest.mark.parametrize("research", [False, True])
def test_lookup_without_matching_evidence_abstains(research: bool) -> None:
    source = ContextFileMetadata(
        file_id="search", filename="Search PRD",
        file_content="Employees can find documents. The travel policy is an example.",
    )
    restricted = ContextFileMetadata(
        file_id="restricted", filename="Travel policy",
        file_content="The annual employee travel allowance is 500 USD.",
    )
    answer = select_excerpts(
        "What is the annual employee travel allowance in USD?",
        [source, restricted], {"search": 1}, research=research,
    )

    assert "no verified passages" in answer.lower()
    assert "Search PRD" not in answer and "500 USD" not in answer
    assert not extract_citation_order_from_text(answer)


def test_research_groups_passages_and_reports_only_one_document() -> None:
    first = ContextFileMetadata(
        file_id="policy", filename="Revision 1", file_content="Procurement approves within five days.",
    )
    follow_up = first.model_copy(update={"file_content": "An appeal deadline is unavailable."})
    answer = select_excerpts(
        "Compare revisions", [first, follow_up, first],
        {"policy": 3, "previous-revision": 8}, research=True,
    )

    assert answer.startswith("## Research brief")
    assert "Only one document is represented" in answer
    assert answer.count("### Revision 1") == 1
    assert answer.count("Procurement approves within five days.") == 1
    assert "An appeal deadline is unavailable." in answer
    assert extract_citation_order_from_text(answer) == [3]


def test_comparison_keeps_qualified_evidence_in_long_passages() -> None:
    first = ContextFileMetadata(
        file_id="search", filename="Search PRD",
        file_content="Index entries may appear in several libraries. " * 16
        + "Recheck access at follow-up retrieval and resource open.",
    )
    second = ContextFileMetadata(
        file_id="handoff", filename="Chat handoff plan",
        file_content="Pass the selected scope through the composer. " * 16
        + "If access is revoked, cite only the remaining permitted evidence.",
    )

    answer = select_excerpts(
        "Compare how Search and Chat recheck access",
        [first, second], {"search": 1, "handoff": 2}, research=True,
    )

    assert "Recheck access at follow-up retrieval and resource open." in answer
    assert "If access is revoked, cite only the remaining permitted evidence." in answer
    assert extract_citation_order_from_text(answer) == [1, 2]


def test_research_with_no_retrieved_passages_does_not_answer_from_history() -> None:
    answer = select_excerpts(
        "What is the deadline?", [],
        {"previous-revision": 8}, research=True,
    )
    assert "no verified passages" in answer
    assert not extract_citation_order_from_text(answer)


@pytest.mark.parametrize("question", [
    "At which points is the requesting user's access evaluated again after the initial Search result?",
    "Does a reader's permission get checked again on a follow-up or when opening an item?",
    "If someone returns to a result or asks about it in a later message, when does NortPole validate that they can view it?",
])
def test_access_lookup_matches_rephrased_operation(question: str) -> None:
    relevant = ContextFileMetadata(
        file_id="search", filename="Search PRD",
        file_content="Recheck at follow-up retrieval and resource open.",
    )
    unrelated = relevant.model_copy(update={
        "file_id": "other", "file_content": "Review the test matrix for reader and non-reader access.",
    })
    answer = select_excerpts(question, [unrelated, relevant], {"search": 1, "other": 2})
    assert relevant.file_content in answer
    assert "test matrix" not in answer
    assert extract_citation_order_from_text(answer) == [1]


@pytest.mark.parametrize("question", [
    "Does a saved task draft begin executing by itself?",
    "Can I leave a workflow request saved without kicking off the job?",
    "What must a practitioner do after composing the request to actually get it underway?",
])
def test_draft_lookup_excludes_workflow_retry_rule(question: str) -> None:
    relevant = ContextFileMetadata(
        file_id="workflow", filename="Workflow PRD",
        file_content="A practitioner saves a task draft, then explicitly starts a run. Saving the draft dispatches no work.",
    )
    retry = relevant.model_copy(update={
        "file_id": "retry", "file_content": "Runs can retry a failure when the saved workflow has no draft.",
    })
    answer = select_excerpts(question, [retry, relevant], {"workflow": 1, "retry": 2})
    assert "explicitly starts a run" in answer
    assert "retry a failure" not in answer
    assert extract_citation_order_from_text(answer) == [1]
