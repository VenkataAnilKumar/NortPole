from nortpole.chat.verified_comparison import compare_passages


def test_supplier_comparison_uses_explicit_clauses() -> None:
    documents = {
        "older": [
            "Procurement approves standard suppliers in 5 business days.",
            "Compliance reviews high-risk suppliers before activation.",
            "The policy does not set an appeal deadline.",
        ],
        "newer": [
            "Vendor Operations approves standard suppliers in 3 business days.",
            "Compliance still reviews high-risk suppliers before activation.",
            "Emergency exceptions require Director approval.",
            "The policy does not set an appeal deadline.",
        ],
    }
    findings = {item.label: item for item in compare_passages("Compare the revisions", documents)}
    assert findings["Approver for standard suppliers"].values == {
        "older": "Procurement", "newer": "Vendor Operations",
    }
    assert not findings["Approval window for standard suppliers"].agrees
    assert findings["Reviewer before activation for high-risk suppliers"].agrees
    assert findings["Repeated statement"].values == {
        "older": "The policy does not set an appeal deadline.",
        "newer": "The policy does not set an appeal deadline.",
    }


def test_labeled_values_preserve_units_and_require_all_documents() -> None:
    findings = compare_passages("What changed?", {
        "a": ["Renewal notice: 30 calendar days.", "Contract term: 12 months."],
        "b": ["Renewal notice: 30 business days.", "Contract term: 12 months.", "Contract term: 24 months."],
        "c": ["Renewal notice: 30 calendar days."],
    })
    assert len(findings) == 1
    assert findings[0].label == "Renewal notice"
    assert findings[0].values["b"] == "30 business days."
    assert not findings[0].agrees


def test_comparison_requires_distinct_sources_and_explicit_intent() -> None:
    two_sources = {"a": ["Notice: 30 days."], "b": ["Notice: 45 days."]}
    assert not compare_passages("What is the notice period?", two_sources)
    assert not compare_passages("Compare the notice periods", {"a": ["Notice: 30 days.", "Notice: 45 days."]})


def test_qualified_rule_is_left_as_an_excerpt() -> None:
    documents = {
        "a": ["Procurement approves standard suppliers in 5 business days."],
        "b": ["Operations approves standard suppliers in 3 business days unless a director is unavailable."],
    }
    assert not compare_passages("Compare the approval deadline", documents)


def test_markdown_runbook_labels_match_plain_values() -> None:
    findings = compare_passages("Compare the runbooks", {
        "a": ["- **Acknowledgement target:** 15 minutes.", "1. __Review cadence__: Quarterly."],
        "b": ["* Acknowledgement target: 10 minutes.", "**Review cadence**: Quarterly."],
    })
    assert [(item.label, item.agrees) for item in findings] == [
        ("Acknowledgement target", False), ("Review cadence", True),
    ]
    assert findings[0].values == {"a": "15 minutes.", "b": "10 minutes."}
