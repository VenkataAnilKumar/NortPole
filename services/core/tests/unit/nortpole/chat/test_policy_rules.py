from uuid import uuid4

import pytest

from nortpole.chat import policy_rules
from nortpole.chat.policy_rules import (
    ABSTENTION,
    PolicyConfiguration,
    PolicyRule,
    PolicyRuleInput,
    render_policy_answer,
    resolve_policy_answer,
    supports_rule,
)
from nortpole.file_store.models import ContextFileMetadata


def rule_for(doc_id: str, *, value: str = "72", unit: str | None = "hours", excerpt: str | None = None):
    return PolicyRuleInput(
        questions=["How many hours does an unused invitation last?"],
        action="expire_invitation",
        conditions={"status": "unused"},
        answer_field="duration",
        value=value,
        unit=unit,
        excerpt=excerpt or f"An unused invitation expires after {value} {unit}.",
        source={"document_id": doc_id, "chunk_id": 0},
    )


@pytest.mark.parametrize("quantity", ["172", "1,072", "72.5", "-72", "−72"])
def test_quote_cannot_support_part_of_a_quantity(quantity):
    rule = rule_for("doc", unit=None, excerpt=f"The limit is {quantity}.")
    passage = ContextFileMetadata(file_id="doc", filename="Limits", file_content=rule.excerpt)
    assert not supports_rule(rule, passage)


def test_policy_answer_requires_current_agreeing_authorized_rules(monkeypatch):
    specs = [rule_for("ordinary"), rule_for("exception", value="48")]
    rules = [PolicyRule(**spec.model_dump(), id=uuid4(), fingerprint="original") for spec in specs]
    available = {
        spec.source.document_id: ContextFileMetadata(
            file_id=spec.source.document_id, filename="Policy", file_content=spec.excerpt,
        )
        for spec in specs
    }
    monkeypatch.setattr(policy_rules, "current_fingerprint", lambda _: "original")
    monkeypatch.setattr(
        policy_rules, "resolve_library_passage",
        lambda source, *_: available.get(source.document_id),
    )
    libraries = [(1, PolicyConfiguration(enabled=True, rules=rules))]
    question = specs[0].questions[0]
    result, _, _ = resolve_policy_answer(question, libraries, None, None, None)
    assert render_policy_answer(result, {}) == ABSTENTION

    available.pop("exception")
    result, passage, library = resolve_policy_answer(question.upper(), libraries, None, None, None)
    assert passage == available["ordinary"] and library == 1
    assert render_policy_answer(result, {"ordinary": 1}) == f"**72 hours**\n\n“{specs[0].excerpt}” [[1]]"
    assert render_policy_answer(result, {}) == ABSTENTION

    for query, selection in (
        (question.removesuffix("?") + " in Canada?", None),
        (question, [specs[1].source]),
    ):
        result, passage, _ = resolve_policy_answer(query, libraries, None, None, selection)
        assert passage is None and render_policy_answer(result, {}) == ABSTENTION

    monkeypatch.setattr(policy_rules, "current_fingerprint", lambda _: "changed")
    result, passage, _ = resolve_policy_answer(question, libraries, None, None, None)
    assert passage is None and render_policy_answer(result, {}) == ABSTENTION


def threshold_rule(phrase="above", *, comparison="gt", value="25", unit="dollars"):
    excerpt = f"Employees must attach receipts for expenses {phrase} {value} {unit}."
    return PolicyRule(
        id=uuid4(),
        fingerprint="current",
        questions=["Does a travel expense of ${amount} meet the receipt threshold?"],
        action="attach receipt",
        conditions={"policy": "travel"},
        answer_field="threshold",
        value=value,
        unit=unit,
        threshold_comparison=comparison,
        excerpt=excerpt,
        source={"document_id": "travel", "chunk_id": 0},
    )


@pytest.mark.parametrize(
    ("phrase", "comparison", "matches"),
    [
        ("above", "gt", (False, False, True)),
        ("at least", "gte", (False, True, True)),
        ("below", "lt", (True, False, False)),
        ("at most", "lte", (True, True, False)),
    ],
)
def test_threshold_comparisons_at_the_boundary(monkeypatch, phrase, comparison, matches):
    rule = threshold_rule(phrase, comparison=comparison)
    excerpt = ContextFileMetadata(file_id="travel", filename="Travel", file_content=rule.excerpt)
    monkeypatch.setattr(policy_rules, "current_fingerprint", lambda _: "current")
    monkeypatch.setattr(policy_rules, "resolve_library_passage", lambda *_: excerpt)
    libraries = [(1, PolicyConfiguration(enabled=True, rules=[rule]))]

    for amount, expected in zip(("24.99", "25.00", "25.01"), matches, strict=True):
        question = rule.questions[0].replace("{amount}", amount)
        result, passage, _ = resolve_policy_answer(question, libraries, None, None, [rule.source])
        assert passage == excerpt
        assert result.value.startswith("The amount meets" if expected else "The amount does not meet")
        assert render_policy_answer(result, {"travel": 1}).endswith(" [[1]]")


def test_threshold_requires_the_authored_phrasing_and_current_selected_evidence(monkeypatch):
    rule = threshold_rule()
    other = threshold_rule("at least", comparison="gte")
    available = {
        1: ContextFileMetadata(file_id="travel", filename="Travel", file_content=rule.excerpt),
        2: ContextFileMetadata(file_id="travel", filename="Travel", file_content=other.excerpt),
    }
    monkeypatch.setattr(policy_rules, "current_fingerprint", lambda _: "current")
    monkeypatch.setattr(policy_rules, "resolve_library_passage", lambda _source, library_id, *_: available.get(library_id))
    libraries = [(1, PolicyConfiguration(enabled=True, rules=[rule]))]
    question = rule.questions[0].replace("{amount}", "25")

    for rejected in (
        question.replace("?", " for international trips?"),
        question.replace("$25", "CAD 25"),
        question.replace("$25", "$-25"),
        question.replace("$25", "$25 + 1"),
    ):
        result, _, _ = resolve_policy_answer(rejected, libraries, None, None, None)
        assert result.document_id is None

    for configured, selection in (
        (libraries, []),
        (libraries + [(2, PolicyConfiguration(enabled=True, rules=[other]))], None),
    ):
        result, _, _ = resolve_policy_answer(question, configured, None, None, selection)
        assert result.document_id is None

    available.pop(1)
    result, _, _ = resolve_policy_answer(question, libraries, None, None, None)
    assert result.document_id is None


@pytest.mark.parametrize("text", [
    "Expenses at least 25 dollars need a receipt.",
    "A receipt is not required for expenses above 25 dollars.",
    "Employees must attach receipts for expenses above 25 dollars or equal to that amount.",
    "Employees must attach receipts for expenses above 25.5 dollars.",
])
def test_wrong_or_qualified_comparison_does_not_support_threshold(text):
    spec = threshold_rule().model_dump() | {"excerpt": "above 25 dollars"}
    rule = PolicyRule.model_validate(spec)
    passage = ContextFileMetadata(file_id="travel", filename="Travel", file_content=text)
    assert not supports_rule(rule, passage)


@pytest.mark.parametrize(("comparison", "phrase"), [("gte", "more"), ("lte", "less")])
def test_inclusive_comparison_can_follow_the_amount(comparison, phrase):
    text = f"Employees must attach receipts for expenses of $25 or {phrase}."
    spec = threshold_rule(comparison=comparison).model_dump()
    rule = PolicyRule.model_validate(spec | {"value": "$25", "unit": None, "excerpt": text})
    passage = ContextFileMetadata(file_id="travel", filename="Travel", file_content=text)
    assert supports_rule(rule, passage)


def test_policy_amounts_render_as_currency_in_markdown():
    answer = policy_rules.PolicyAnswer(document_id="travel", value="At least $25", excerpt="Expenses of $25 or more.")
    rendered = render_policy_answer(answer, {"travel": 1})
    assert rendered == r"**At least \$25**" + "\n\n" + r"“Expenses of \$25 or more.” [[1]]"
