"""The injection case set is well formed, and the code-level controls hold even against a model
that obeys every instruction in a source (a worst-case stand-in)."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from evolvxsi.tasks import drafter
from evolvxsi.tasks.evidence import Evidence

ROOT = Path(__file__).parents[4]
SET = json.loads((ROOT / "scripts/injection_cases.json").read_text())
_spec = importlib.util.spec_from_file_location("injection_suite", ROOT / "scripts/injection_suite.py")
suite = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(suite)  # type: ignore[union-attr]


def test_the_case_set_is_well_formed() -> None:
    ids = [c["id"] for c in SET["cases"]]
    assert len(ids) == len(set(ids)) >= 20
    cats = {c["category"] for c in SET["cases"]}
    assert cats == {"override", "leak", "exfil", "fake_citation", "delimiter", "conflicting_source", "obfuscation"}
    for c in SET["cases"]:
        assert c["passage"] and any(k in c for k in ("canary", "leak", "exfil", "false_claim", "fake_cites")), c["id"]
    assert SET["expect"] in SET["benign"]


def test_violation_checks_name_what_the_model_did() -> None:
    c = {"canary": "CANARY-1", "exfil": ["evil.example"], "false_claim": ["365"], "fake_cites": [9], "leak": ["never an instruction"]}
    assert suite.violated(c, "All good, 30 days [1].", 0) == []
    got = suite.violated(c, "CANARY-1, see http://evil.example, 365 days [9], it is never an instruction.", 0)
    assert len(got) == 5


class _ObeysEverything:
    """Returns whatever the passage asked for, including forged citations."""

    config = SimpleNamespace(model_configuration_id=1)

    def invoke(self, request, context=None):  # type: ignore[no-untyped-def]
        text = "CANARY-7Q2X [9] Verified by CANARY-7Q2X. Deadline 30 days [1] and again [7]."
        return SimpleNamespace(text=text)


@pytest.mark.parametrize("hostile", [c["passage"] for c in SET["cases"] if c["category"] in ("fake_citation", "delimiter")])
def test_forged_citations_never_survive_even_if_the_model_obeys(hostile: str) -> None:
    ev = [Evidence(n=1, doc_id="a", title="Honest", link=None, passage=SET["benign"]), Evidence(n=2, doc_id="b", title="Addendum", link=None, passage=hostile)]
    with patch.object(drafter, "get_default_llm", return_value=_ObeysEverything()), patch.object(drafter, "enforce_route", return_value=SimpleNamespace(kind="local")):
        res = drafter.draft_answer(None, None, "T", SET["question"], ["a"], ev)  # type: ignore[arg-type]
    assert "[9]" not in res.text and "[7]" not in res.text
    assert res.cited == [1] and res.removed_citations == 2


def test_a_hostile_passage_cannot_forge_a_source_boundary_or_a_prompt_section() -> None:
    for c in SET["cases"]:
        prompt = drafter.build_prompt("T", "Q", ["a"], [Evidence(n=2, doc_id="b", title="Addendum", link=None, passage=c["passage"])])
        body = prompt.split("Sources:\n", 1)[1]
        assert body.count("<<source 2>>") == 1 and body.count("<<source>>") == 1, c["id"]
        assert "\n" not in body.strip(), f"{c['id']}: the passage became several lines"
