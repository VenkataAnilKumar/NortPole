import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from nortpole.chat.document_review import DocumentReview, VerifiedFinding, compare_revision, review_document
from nortpole.context.search.models import BaseFilters
from nortpole.file_store.models import ContextFileMetadata
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.llm.interfaces import LLMUserIdentity
from nortpole.server.query_and_chat.models import SendMessageRequest
from nortpole.work.packs.document_review import rules_for_document_review

DOCUMENT = "The department manager approves reimbursements."
POLICY = "Finance approves reimbursements."
SOURCE = ContextFileMetadata(file_id="policy", filename="Reimbursement policy", file_content=POLICY)
IDENTITY = LLMUserIdentity(user_id="test", session_id="session")


def model_with_findings(*findings):
    model = Mock()
    model.config.max_input_tokens = 8192
    model.invoke.return_value = SimpleNamespace(text=json.dumps({"findings": list(findings)}))
    return model


def test_conflicts_only_use_the_actual_policy_citation_and_never_call_tools():
    model = model_with_findings({
        "status": "conflict", "explanation": "The approval role differs.",
        "document_quote": DOCUMENT, "source": 1, "policy_quote": POLICY,
    })
    result = review_document(model, IDENTITY, len, DOCUMENT, [SOURCE], "", [], None)
    assert result.needs_review
    assert "Potential conflicts" in result.answer({"policy": 7})
    assert "The approval role differs. [[7]]" in result.answer({"policy": 7})
    assert not model.invoke.call_args.args[0].tools


def test_fabricated_quotes_cannot_appear_as_verified_findings():
    model = model_with_findings({
        "status": "aligned", "explanation": "Invented conclusion [[10]]",
        "document_quote": DOCUMENT, "source": 1, "policy_quote": "Anyone approves.",
    })
    result = review_document(model, IDENTITY, len, DOCUMENT, [SOURCE], "", [], None)
    assert result.needs_review
    assert not result.findings
    assert "Invented" not in result.answer({"policy": 7})
    assert "lacked matching" in result.answer({"policy": 7})


def test_pack_rules_flag_human_review_and_missing_evidence_skips_model():
    model = model_with_findings({
        "status": "aligned", "explanation": "Same approval rule.",
        "document_quote": POLICY, "source": 1, "policy_quote": POLICY,
    })
    rule = {"kind": "min_citations", "value": 2, "severity": "block", "message": "Find a second policy."}
    result = review_document(model, IDENTITY, len, POLICY, [SOURCE], "", [rule], "Finance (1)")
    assert result.needs_review
    assert "Finance (1)" in result.answer({"policy": 7})
    assert "Find a second policy." in result.answer({"policy": 7})
    model.invoke.reset_mock()
    assert review_document(model, IDENTITY, len, POLICY, [], "", [], None).needs_review
    model.invoke.assert_not_called()


def test_guided_request_requires_a_supported_attachment_and_one_library():
    options = {
        "message": "Review this policy",
        "document_review": True,
        "ground_selected_knowledge": True,
        "file_descriptors": [{"id": "file", "type": "plain_text", "name": "draft.txt"}],
    }
    with pytest.raises(ValidationError, match="one Knowledge library"):
        SendMessageRequest(**options)
    options["internal_search_filters"] = BaseFilters(document_set=["Travel"])
    assert SendMessageRequest(**options).document_review
    options["file_descriptors"][0]["name"] = "screenshot.png"
    with pytest.raises(ValidationError, match="one PDF"):
        SendMessageRequest(**options)


def test_revision_requires_same_evidence_and_a_verified_document_change():
    old = VerifiedFinding(
        status="conflict", explanation="Incorrect approver.", source_id="policy",
        document_quote=DOCUMENT, policy_quote=POLICY,
    )
    fixed = VerifiedFinding(
        status="aligned", explanation="The approver matches.", source_id="policy",
        document_quote="Finance approves reimbursements.", policy_quote=POLICY,
    )
    finding = VerifiedFinding(status="needs_review", explanation="Check retention.")
    revised = DocumentReview(findings=[fixed, finding])
    comparison = compare_revision(4, [(1, old), (2, VerifiedFinding(status="needs_review", explanation="Check date."))], revised)
    assert comparison.previous_id == 4
    assert [(item.previous_number, item.revised_number, item.addressed) for item in comparison.findings] == [
        (1, 1, True), (2, None, False),
    ]
    assert comparison.new_findings == [2]
    fixed.policy_quote = "Treasury approves reimbursements."
    assert not compare_revision(4, [(1, old)], revised).findings[0].addressed


def test_revision_refuses_to_silently_change_pack_versions():
    db = Mock()
    db.scalar.return_value = SimpleNamespace(version="2.0.0")
    with pytest.raises(NortPoleError, match="original pack version is no longer active"):
        rules_for_document_review(db, "travel-pack", 123, required_version="1.0.0")


def test_revision_can_verify_literal_replacement_omitted_by_model():
    old_quote = "Expenses strictly over $75 do not require a receipt."
    corrected = "Expenses strictly over $75 require a receipt."
    policy = "Test policy, version 1. " + corrected
    source = ContextFileMetadata(file_id="policy", filename="Receipt policy", file_content=policy)
    old = VerifiedFinding(
        status="conflict", explanation="Receipt rules differ.", source_id="policy",
        document_quote=old_quote, policy_quote=policy,
    )
    model = model_with_findings()
    report = review_document(
        model, IDENTITY, len, corrected, [source], "", [], None, previous_findings=[old],
    )
    assert compare_revision(1, [(1, old)], report).findings[0].addressed
    unchanged = review_document(
        model, IDENTITY, len, old_quote + " " + corrected, [source], "", [], None, previous_findings=[old],
    )
    assert not compare_revision(1, [(1, old)], unchanged).findings[0].addressed
