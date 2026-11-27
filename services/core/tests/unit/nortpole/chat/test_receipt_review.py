from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from nortpole.chat.receipt_review import prepare_receipt_review
from nortpole.configs.constants import DocumentSource
from nortpole.context.search.models import SearchDoc
from nortpole.file_store.models import ContextFileMetadata
from nortpole.server.query_and_chat.models import SendMessageRequest


def policy(
    text: str, title: str = "Travel Receipt Policy", document_id: str = "policy"
) -> ContextFileMetadata:
    return ContextFileMetadata(
        file_id=document_id,
        filename=title,
        file_content=text,
        source_document=SearchDoc(
            document_id=document_id, chunk_ind=0, semantic_identifier=title,
            link="https://example.invalid/policy", blurb=text,
            source_type=DocumentSource.INGESTION_API, boost=1, hidden=False,
            metadata={}, match_highlights=[],
        ),
    )


def expenses(text: str) -> ContextFileMetadata:
    return ContextFileMetadata(file_id="csv", filename="expenses.csv", file_content=text)


def test_receipt_review_uses_exact_named_policy_and_computes_each_row() -> None:
    rules = (
        "Travel Receipt Policy, version 1. Expenses strictly over $75 require a receipt. "
        "Expenses of $75 or less do not require a receipt."
    )
    csv = "row_id,expense,amount_usd,receipt\nE1,Hotel,120,no\nE2,Taxi,95,yes\nE3,Meal,40,no\nE4,Train,75,no"
    review = prepare_receipt_review(
        "Which expenses violate the Travel Receipt Policy?",
        [
            policy(rules),
            policy("Expenses over $25 require a receipt.", "Other Policy", "other"),
            expenses(csv),
        ],
    )
    assert review and review.source_id == "policy"
    assert review.threshold == Decimal("75")
    answer = review.answer(3)
    assert "[[3]]" in answer
    assert "**Violations** · `E1`\n" in answer
    assert "| `E2` | $95.00 | Complies. A receipt is required and one is recorded. |" in answer
    assert "| `E4` | $75.00 | Complies. The amount falls outside" in answer


def test_inclusive_threshold_uses_decimal_amounts() -> None:
    review = prepare_receipt_review(
        "Check the receipt policy",
        [
            policy("Expenses at least $75.10 require a receipt."),
            expenses("id,amount_usd,has_receipt\nA,75.10,no\nB,75.09,no"),
        ],
    )
    assert review and review.inclusive
    assert "**Violations** · `A`\n" in review.answer()


def test_conflicting_or_conditional_policies_need_clarification() -> None:
    csv = expenses("amount_usd,receipt\n90,no")
    conflicting = prepare_receipt_review(
        "Check the receipt policy",
        [csv, policy("Expenses above $75 require a receipt. Expenses over $80 require a receipt.")],
    )
    conditional = prepare_receipt_review(
        "Check the receipt policy",
        [csv, policy("Expenses over $75 require a receipt. Exceptions apply to meals.")],
    )
    assert conflicting and conflicting.clarification
    assert conditional and conditional.clarification


def test_unrelated_request_uses_normal_chat() -> None:
    assert prepare_receipt_review("Summarize these expenses", []) is None


def test_invalid_receipt_cell_needs_clarification() -> None:
    review = prepare_receipt_review(
        "Check the receipt policy",
        [
            policy("Expenses over $75 require a receipt."),
            expenses("id,amount_usd,receipt\nA,90,"),
        ],
    )
    assert review and review.clarification


def test_receipt_review_does_not_ignore_unloaded_csvs() -> None:
    review = prepare_receipt_review(
        "Check the receipt policy",
        [
            policy("Expenses over $75 require a receipt."),
            expenses("id,amount_usd,receipt\nA,90,no"),
        ],
        attached_csv_count=2,
    )
    assert review and review.clarification


def test_explicit_workflow_uses_only_the_selected_policy_title() -> None:
    sources = [
        policy("Expenses over $75 require a receipt."),
        policy("Expenses over $25 require a receipt.", "Other Policy", "other"),
        expenses("id,amount_usd,receipt\nA,75,no\nB,76,no"),
    ]
    review = prepare_receipt_review(
        "Workflow run", sources, policy_title="travel receipt policy"
    )
    assert review and review.source_id == "policy"
    assert "**Violations** · `B`\n" in review.answer()

    missing = prepare_receipt_review(
        "Workflow run", sources, policy_title="Missing Policy"
    )
    assert missing and missing.clarification and missing.source_id is None

    ambiguous = prepare_receipt_review("Workflow run", sources, policy_title="")
    assert ambiguous and ambiguous.clarification and ambiguous.source_id is None


@pytest.mark.parametrize(
    ("override", "error"),
    [
        ({"ground_selected_knowledge": False}, "one Knowledge library"),
        ({"internal_search_filters": {"document_set": ["One", "Two"]}}, "one Knowledge library"),
        ({"file_descriptors": []}, "one CSV attachment"),
        ({"deep_research": True}, "single chat response"),
    ],
)
def test_expense_workflow_request_requires_one_policy_scope_and_one_csv(
    override: dict, error: str
) -> None:
    body = {
        "chat_session_id": uuid4(),
        "message": "Workflow run",
        "receipt_review_policy_title": "",
        "ground_selected_knowledge": True,
        "internal_search_filters": {"document_set": ["One"]},
        "file_descriptors": [{"id": "csv", "type": "tabular", "name": "expenses.csv"}],
    }
    assert SendMessageRequest.model_validate(body).receipt_review_policy_title == ""
    with pytest.raises(ValidationError, match=error):
        SendMessageRequest.model_validate(body | override)
