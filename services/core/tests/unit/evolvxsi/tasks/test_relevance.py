from unittest.mock import MagicMock, patch

from evolvxsi.work.tasks.evidence import Evidence
from evolvxsi.work.tasks.relevance import filter_relevant, parse_verdict


def _ev(n: int, doc: str, text: str = "x") -> Evidence:
    return Evidence(n=n, doc_id=doc, title=doc, link=None, passage=text)


def _llm(verdicts):  # type: ignore[no-untyped-def]
    llm = MagicMock()
    llm.config.model_configuration_id = 1
    it = iter(verdicts)

    def invoke(req, context=None):  # type: ignore[no-untyped-def]
        v = next(it)
        if isinstance(v, Exception):
            raise v
        r = MagicMock()
        r.text = v
        return r

    llm.invoke.side_effect = invoke
    return llm


def _run(verdicts, ev):  # type: ignore[no-untyped-def]
    with patch("evolvxsi.work.tasks.relevance.get_default_llm", return_value=_llm(verdicts)), \
         patch("evolvxsi.work.tasks.relevance.enforce_route"):
        return filter_relevant(MagicMock(), MagicMock(), "q", ev)


def test_verdict_parsing() -> None:
    assert parse_verdict("Yes") and parse_verdict("yes, it does") and parse_verdict("  YES.")
    assert not parse_verdict("no") and not parse_verdict("") and not parse_verdict("maybe yes")


def test_only_relevant_passages_stay_and_are_renumbered() -> None:
    out = _run(["no", "yes", "yes"], [_ev(1, "a"), _ev(2, "b"), _ev(3, "c")])
    assert [(e.n, e.doc_id) for e in out] == [(1, "b"), (2, "c")]


def test_nothing_relevant_means_no_evidence() -> None:
    assert _run(["no", "no"], [_ev(1, "a"), _ev(2, "b")]) == []


def test_a_judge_that_fails_does_not_vouch_for_the_passage() -> None:
    out = _run([RuntimeError("model down"), "yes"], [_ev(1, "a"), _ev(2, "b")])
    assert [e.doc_id for e in out] == ["b"]


def test_no_candidates_means_no_calls_and_the_switch_turns_it_off(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    with patch("evolvxsi.work.tasks.relevance.get_default_llm") as g:
        assert filter_relevant(MagicMock(), MagicMock(), "q", []) == []
        g.assert_not_called()
        monkeypatch.setenv("EVOLVXSI_RELEVANCE_CHECK", "false")
        ev = [_ev(1, "a")]
        assert filter_relevant(MagicMock(), MagicMock(), "q", ev) == ev
        g.assert_not_called()


def test_a_blocked_route_stops_before_any_passage_is_sent() -> None:
    from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
    from evolvxsi.error_handling.exceptions import EvolvXSIError
    import pytest

    llm = _llm([])
    with patch("evolvxsi.work.tasks.relevance.get_default_llm", return_value=llm), \
         patch("evolvxsi.work.tasks.relevance.enforce_route", side_effect=EvolvXSIError(EvolvXSIErrorCode.POLICY_BLOCKED, "blocked")):
        with pytest.raises(EvolvXSIError):
            filter_relevant(MagicMock(), MagicMock(), "q", [_ev(1, "a")])
    llm.invoke.assert_not_called()
