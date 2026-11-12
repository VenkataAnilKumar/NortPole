"""Pack evaluation cases: what counts as a pass."""

from types import SimpleNamespace
from unittest.mock import patch

from evolvxsi.packs import evaluation
from evolvxsi.packs.manifest import EvalCase
from evolvxsi.tasks.drafter import NO_SOURCE_TEXT


def _run(case: EvalCase, text: str, cited: list[int]):  # type: ignore[no-untyped-def]
    with patch.object(evaluation, "draft_answer", return_value=SimpleNamespace(text=text, cited=cited)):
        return evaluation._run_case(None, None, case, "Pack")  # type: ignore[arg-type]


def test_a_case_passes_with_expected_text_and_a_citation() -> None:
    c = EvalCase(question="Days?", expect="30 days", evidence=["Due in 30 days."])
    assert _run(c, "Within 30 days [1].", [1]).passed
    assert not _run(c, "Within 30 days.", []).passed
    assert not _run(c, "Soon [1].", [1]).passed


def test_a_case_without_evidence_must_say_no_source_covers_it() -> None:
    c = EvalCase(question="Board takeover?", expect="No source", evidence=[])
    assert _run(c, NO_SOURCE_TEXT, []).passed
    assert not _run(c, "No source, but probably yes.", []).passed


def test_a_model_failure_fails_the_case_instead_of_crashing() -> None:
    c = EvalCase(question="Q", expect="x", evidence=["x"])
    with patch.object(evaluation, "draft_answer", side_effect=RuntimeError("down")):
        r = evaluation._run_case(None, None, c, "Pack")  # type: ignore[arg-type]
    assert not r.passed and "RuntimeError" in r.reason
