"""Pack review rules: what each kind checks, and which ones the manifest accepts."""

import pytest
from pydantic import ValidationError

from evolvxsi.work.packs.manifest import ReviewRule
from evolvxsi.work.packs.review_rules import blocking_failures, evaluate

SRC = [{"n": 1}, {"n": 2}]


def _r(kind, value=None, severity="block"):  # type: ignore[no-untyped-def]
    return {"kind": kind, "value": value, "severity": severity, "message": f"{kind} rule"}


def test_each_kind_passes_and_fails_as_named() -> None:
    text = "Receipts are due in 30 days [1][2]."
    ok = evaluate([_r("min_citations", 2), _r("max_words", 20), _r("must_include", "30 DAYS"), _r("must_not_include", "guarantee"), _r("all_claims_supported")],
                  text, SRC, [{"status": "supported"}])
    assert all(x["passed"] for x in ok)
    bad = evaluate([_r("min_citations", 3), _r("max_words", 3), _r("must_include", "director"), _r("must_not_include", "30 days"), _r("all_claims_supported")],
                   text, SRC, [{"status": "unsupported"}])
    assert not any(x["passed"] for x in bad)
    assert [x["detail"] for x in bad][:2] == ["2 cited", "7 words"]


def test_citations_count_what_the_text_cites_not_what_was_gathered() -> None:
    gathered = [{"n": 1}, {"n": 2}, {"n": 3}]
    assert evaluate([_r("min_citations", 2)], "One [1] and again [1], an unknown [9].", gathered, [])[0]["detail"] == "1 cited"
    assert evaluate([_r("min_citations", 2)], "Both [1][3].", gathered, [])[0]["passed"]


def test_only_failed_block_rules_stop_approval() -> None:
    res = evaluate([_r("min_citations", 5, "warn"), _r("must_include", "zzz", "block")], "text", [], [])
    assert [x["kind"] for x in blocking_failures(res)] == ["must_include"]


def test_no_rules_means_no_results_and_no_blocks() -> None:
    assert evaluate(None, "x", [], []) == [] and blocking_failures([]) == []


def test_an_unknown_rule_in_a_stored_snapshot_fails_closed() -> None:
    res = evaluate([{"kind": "run_code", "severity": "block", "message": "m"}], "x", [], [])
    assert not res[0]["passed"] and blocking_failures(res)


@pytest.mark.parametrize("bad", [
    dict(kind="min_citations", value=0), dict(kind="min_citations", value="2"), dict(kind="min_citations", value=True),
    dict(kind="max_words", value=5), dict(kind="max_words", value=9999),
    dict(kind="must_include", value=""), dict(kind="must_include", value=5), dict(kind="must_not_include", value="x" * 101),
    dict(kind="all_claims_supported", value=1), dict(kind="exec", value="rm -rf /"),
])
def test_the_manifest_refuses_rules_that_do_not_fit_their_kind(bad: dict) -> None:
    with pytest.raises(ValidationError):
        ReviewRule(message="m", **bad)


def test_valid_rules_are_accepted_and_severity_defaults_to_block() -> None:
    assert ReviewRule(kind="min_citations", value=2, message="m").severity == "block"
    assert ReviewRule(kind="all_claims_supported", message="m").value is None
    with pytest.raises(ValidationError):
        ReviewRule(kind="max_words", value=100, message="m", extra_field=1)  # type: ignore[call-arg]
