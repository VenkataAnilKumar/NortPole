from types import SimpleNamespace

from evolvxsi.tasks.drafter import build_prompt, keep_valid_citations
from evolvxsi.tasks.evidence import Evidence, chunks_to_evidence


def test_citations_to_unknown_sources_are_removed() -> None:
    text, cited, removed = keep_valid_citations("Receipts are due in 30 days [1]. Flights are economy [7].", {1, 2})
    assert text == "Receipts are due in 30 days [1]. Flights are economy."
    assert cited == [1] and removed == 1


def test_cited_order_is_first_use_and_unique() -> None:
    _, cited, _ = keep_valid_citations("a [2] b [1] c [2]", {1, 2})
    assert cited == [2, 1]


def test_no_sources_means_every_citation_goes() -> None:
    text, cited, removed = keep_valid_citations("Made up [1].", set())
    assert cited == [] and removed == 1 and "[1]" not in text


def test_prompt_lists_sources_or_says_none() -> None:
    ev = [Evidence(n=1, doc_id="d", title="Travel policy", link=None, passage="Receipts in 30 days.")]
    assert "[1] Travel policy: <<source 1>> Receipts in 30 days. <<source>>" in build_prompt("t", "r", ["step"], ev)
    assert "Sources: none" in build_prompt("t", "r", ["step"], [])


def _chunk(doc_id: str, text: str):  # type: ignore[no-untyped-def]
    return SimpleNamespace(document_id=doc_id, semantic_identifier=doc_id.upper(), title=None,
                           source_links={0: f"https://x/{doc_id}"}, content=text, blurb="")


def test_evidence_is_one_entry_per_document_numbered_from_one() -> None:
    ev = chunks_to_evidence([_chunk("a", "1"), _chunk("a", "2"), _chunk("b", "3")])
    assert [(e.n, e.doc_id, e.passage) for e in ev] == [(1, "a", "1"), (2, "b", "3")]
    assert ev[0].link == "https://x/a"


def test_semantic_hits_come_first_and_keyword_adds_only_new_documents() -> None:
    from evolvxsi.tasks.evidence import _merge

    sem = [_chunk("a", "1"), _chunk("b", "2")]
    kw = [_chunk("b", "x"), _chunk("c", "3")]
    assert [c.document_id for c in _merge(sem, kw)] == ["a", "b", "c"]
    assert [c.document_id for c in _merge([], kw)] == ["b", "c"]
