"""Pack evaluation cases: what counts as a pass."""

from types import SimpleNamespace
from unittest.mock import patch

from evolvxsi.work.packs import evaluation
from evolvxsi.work.packs.manifest import EvalCase
from evolvxsi.work.tasks.drafter import NO_SOURCE_TEXT


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


def test_house_style_is_added_below_the_rules_and_only_when_present() -> None:
    from evolvxsi.work.tasks.drafter import STYLE_RULE, build_prompt

    plain = build_prompt("T", "R", ["a"], [])
    styled = build_prompt("T", "R", ["a"], [], style="  Three   short\nsentences.  ")
    assert "House style" not in plain
    assert styled.endswith("House style: Three short sentences.")
    assert "citation rules" in STYLE_RULE


def test_a_style_longer_than_the_limit_is_refused() -> None:
    import pytest
    from pydantic import ValidationError

    from evolvxsi.work.packs.manifest import Template

    with pytest.raises(ValidationError):
        Template(id="t", title="T", request="R", style="x" * 801)


def test_a_case_runs_with_its_templates_style_and_must_name_a_real_template() -> None:
    import json
    from pathlib import Path

    import pytest
    from pydantic import ValidationError

    from evolvxsi.work.packs.manifest import Manifest

    raw = json.loads((Path(__file__).parents[4] / "scripts/sample_packs/finance-policy-review.json").read_text())
    m = Manifest.model_validate(raw)
    seen: list[str] = []

    def fake(db, user, title, question, plan, ev, style="", guides=()):  # type: ignore[no-untyped-def]
        seen.append(style)
        return SimpleNamespace(text="30 days [1]. director. No source you are allowed to open", cited=[1])

    with patch.object(evaluation, "draft_answer", fake):
        evaluation.evaluate(None, None, m)  # type: ignore[arg-type]
    assert seen[0].startswith("Answer in at most three") and seen[1:] == ["", ""]

    raw["evaluation_cases"][0]["template"] = "nope"
    with pytest.raises(ValidationError):
        Manifest.model_validate(raw)
